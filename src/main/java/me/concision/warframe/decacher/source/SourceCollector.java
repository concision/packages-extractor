package me.concision.warframe.decacher.source;

import java.io.IOException;
import java.io.InputStream;
import lombok.NonNull;
import me.concision.warframe.decacher.CommandArguments;

/**
 * An interface for collectors providing the Packages.bin data stream for collecting packages.
 * Streams may be less performant if they are lazily generated.
 *
 * @author Concision
 * @date 10/21/2019
 */
public interface SourceCollector {
    /**
     * Generates a Packages.bin data stream
     *
     * @param args {@link CommandArguments} execution parameters
     * @return a Packages.bin {@link InputStream}
     */
    InputStream generate(@NonNull CommandArguments args) throws IOException;
}