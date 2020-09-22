import asyncio
import json
from asyncio import StreamReader, StreamWriter
from gzip import GzipFile
from io import BytesIO
from typing import Union, TypedDict


class PackageEntry(TypedDict):
    """
    A JSON-deserialized package record produced by the unpacker process with --output RECORDS.
    """

    # the absolute package path of the record
    path: str
    # the package contents
    package: dict


class Unpacker:
    """
    High level Python controller for extracting packages using the unpacker executable. The internal state of the
    initialized object stores part of the logging and output of the executed unpacker processes (up until an exception
    is raised).
    """

    # indicates that this Unpacker instance has already been used
    __consumed: bool = False

    # GZIP compressed byte buffer of raw Packages.bin
    compressed_packages: BytesIO = BytesIO()
    # indicates that the `compressed_packages` is a complete extracted Packages.bin (i.e. not partially extracted)
    successfully_extracted_packages: bool = False

    # verbose logging output from the Packages.bin producing process
    stderr_packages_bin: BytesIO = BytesIO()
    # verbose logging output from the package records producing process
    stderr_package_records: BytesIO = BytesIO()

    async def unpack(self):
        """
        Initializes the unpacker executable to retrieve Packages.bin and produce JSON-serialized package entries. This
        function is an asynchronous generator that yields PackageEntry instances to the caller.
        """

        # ensure this object instance is fresh
        if self.__consumed:
            raise Exception(f"this {Unpacker.__name__} instance has already been consumed")
        # mark instance as consumed
        self.__consumed = True

        # create unpacker process to produce a Packages.bin binary stream
        try:
            process_packages_bin = await asyncio.create_subprocess_exec(
                "java", "-jar", "/unpacker/cli/unpacker.jar",
                "--verbose",
                "--source", "UPDATER",
                "--output", "BINARY",
                limit=4 * 1024 * 1024,  # 4 MB
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            # create unpacker process to accept a Packages.bin binary stream and produce package records
            process_package_records = await asyncio.create_subprocess_exec(
                "java", "-jar", "/unpacker/cli/unpacker.jar",
                "--verbose",
                "--source", "BINARY",
                "--output", "RECORDS",
                limit=16 * 1024 * 1024,  # 16 MB
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
        except FileNotFoundError as exception:
            raise Exception("java for unpacker CLI was not found", exception)

        # pipe `process_packages_bin`'s standard output to `process_package_records`'s standard input AND a byte buffer
        asyncio.create_task(self.__pipe_packages_bin(
            input_stream=process_packages_bin.stdout,
            output_stream=process_package_records.stdin,
        ))
        # capture `process_packages_bin`'s standard error to a byte buffer
        asyncio.create_task(Unpacker.__pipe_stream(
            stream=process_packages_bin.stderr,
            buffer=self.stderr_packages_bin,
        ))
        # capture `process_package_records`'s standard error to a byte buffer
        asyncio.create_task(Unpacker.__pipe_stream(
            stream=process_package_records.stderr,
            buffer=self.stderr_package_records,
        ))

        # process each JSON-serialized package record (as ASCII)
        try:
            while True:
                # read package record
                package_record: bytes = await process_package_records.stdout.readline()
                # end of feed
                if not package_record:
                    break
                # return to iterating caller
                yield json.loads(package_record.decode("ASCII"))
        except Exception as exception:
            raise Exception("an unexpected exception occurred while reading JSON package records", exception)

        # cleanup any dangling processes
        for process in [process_packages_bin, process_package_records]:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        # wait for processes to be fully killed
        await asyncio.gather(process_packages_bin.wait(), process_package_records.wait())

    async def __pipe_packages_bin(self, *, input_stream: StreamReader, output_stream: StreamWriter):
        """
        Pipes the Packages.bin binary input stream to a GZIP compression stream and the package record's standard input
        stream.
        Note: If an underlying I/O exception occurs while piping to the standard input, the bytes will still attempt to
        be fully written to the GZIP compression before raising an exception.
        """

        # if an underlying exception occurred with the pipe, it is stored here
        pipe_exception: Union[Exception, None] = None

        try:
            # initializes a GZIP compression stream with the compressed packages byte buffer
            with GzipFile(mode='wb', fileobj=self.compressed_packages) as compressed_out:
                # read chunk by chunk
                while True:
                    # read a chunk from raw packages binary
                    buffer: bytes = await input_stream.read(256 * 1024)  # 256 kb
                    # check not end-of-feed has NOT been reached
                    if not buffer:
                        # mark Packages.bin as successfully extracted
                        self.successfully_extracted_packages = True
                        break

                    # write chunk to buffer
                    compressed_out.write(buffer)
                    # if the pipe has not been broken, write to it
                    if pipe_exception is None:
                        try:
                            output_stream.write(buffer)
                            await output_stream.drain()
                        except Exception as exception:
                            # mark an exception as occurring
                            pipe_exception = exception
        except Exception as exception:
            raise Exception("an unexpected exception occurred while piping raw Packages.bin binary stream", exception)

        # if an underlying exception occurred with the pipe, raise it
        if pipe_exception is not None:
            raise Exception(
                "an unexpected exception occurred while piping raw Packages.bin binary stream to the package records process",
                # noqa
                # noqa
                exception
            )

    @staticmethod
    async def __pipe_stream(*, stream: StreamReader, buffer: BytesIO):
        """
        Pipes bytes from a StreamReader into a BytesIO byte buffer.
        Note: If an underlying I/O exception occurs during piping, the exception is ignored.
        """

        try:
            # read chunk by chunk
            while True:
                # read a chunk of the stream
                stream_bytes: bytes = await stream.read(16 * 1024)  # 16KB
                # check not end-of-feed has NOT been reached
                if not stream_bytes:
                    break
                # write chunk to buffer
                buffer.write(stream_bytes)
        except:
            pass
