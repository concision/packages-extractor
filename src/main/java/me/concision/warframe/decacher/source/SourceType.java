package me.concision.warframe.decacher.source;

import java.io.IOException;
import java.io.InputStream;
import java.util.function.Supplier;
import lombok.Getter;
import lombok.NonNull;
import lombok.RequiredArgsConstructor;
import me.concision.warframe.decacher.CommandArguments;

/**
 * Specifies the data source for acquiring Packages.bin
 *
 * @author Concision
 * @date 10/7/2019
 */
@RequiredArgsConstructor
public enum SourceType {
    /**
     * Streams directly from Warframe origin server
     */
    ORIGIN(false, OriginSourceCollector::new),
    /**
     * Extracts from Warframe base/packages directory.
     * If no directory argument ({@link CommandArguments#sourcePath}) is specified, searches for default install location
     */
    INSTALL(false, InstallSourceCollector::new),
    /**
     * Extracts from a packages directory. {@link CommandArguments#sourcePath} indicates directory.
     */
    FOLDER(true, FolderSourceCollector::new),
    /**
     * Extracts from a raw Packages.bin file. {@link CommandArguments#sourcePath} indicates file.
     */
    BINARY(true, BinarySourceCollector::new);

    /**
     * Requires an additional {@link CommandArguments#sourcePath}
     */
    @Getter
    private final boolean requiresSource;

    /**
     * Type-specific collector instance generator
     */
    @NonNull
    private final Supplier<SourceCollector> collector;

    /**
     * See {@link SourceCollector#generate(CommandArguments)}
     *
     * @param arguments {@link CommandArguments} execution parameters
     * @return generated Packages.bin data stream
     */
    public InputStream generate(@NonNull CommandArguments arguments) throws IOException {
        return collector.get().generate(arguments);
    }
}