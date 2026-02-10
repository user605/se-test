/*
 * Licensed to the Apache Software Foundation (ASF) under one or more
 * contributor license agreements.  The ASF licenses this file to You
 * under the Apache License, Version 2.0 (the "License"); you may not
 * use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.  For additional information regarding
 * copyright in this work, please see the NOTICE file in the top level
 * directory of this distribution.
 */

package org.apache.roller.weblogger.util;

import java.util.List;
import java.util.Map;
import org.apache.commons.lang3.StringUtils;
import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;
import org.apache.roller.weblogger.business.plugins.entry.WeblogEntryPlugin;
import org.apache.roller.weblogger.pojos.WeblogEntry;

/**
 * Helper class to handle transformation/rendering of weblog entries.
 * Extracted from WeblogEntry to reduce its complexity and coupling.
 */
public final class WeblogEntryTransformer {
    private static final Log mLogger = LogFactory.getLog(WeblogEntryTransformer.class);

    private WeblogEntryTransformer() {
        // utility class
    }

    /**
     * Transform string based on plugins enabled for this weblog entry.
     */
    public static String render(WeblogEntry entry, String str) {
        String ret = str;
        mLogger.debug("Applying page plugins to string");
        Map<String, WeblogEntryPlugin> inPlugins = entry.getWebsite().getInitializedPlugins();
        if (str != null && inPlugins != null) {
            List<String> entryPlugins = entry.getPluginsList();
            
            // if no Entry plugins, don't bother looping.
            if (entryPlugins != null && !entryPlugins.isEmpty()) {
                
                // now loop over mPagePlugins, matching
                // against Entry plugins (by name):
                // where a match is found render Plugin.
                for (Map.Entry<String, WeblogEntryPlugin> pluginEntry : inPlugins.entrySet()) {
                    if (entryPlugins.contains(pluginEntry.getKey())) {
                        WeblogEntryPlugin pagePlugin = pluginEntry.getValue();
                        try {
                            ret = pagePlugin.render(entry, ret);
                        } catch (Exception e) {
                            mLogger.error("ERROR from plugin: " + pagePlugin.getName(), e);
                        }
                    }
                }
            }
        } 
        return HTMLSanitizer.conditionallySanitize(ret);
    }

    public static String getTransformedText(WeblogEntry entry) {
        return render(entry, entry.getText());
    }

    public static String getTransformedSummary(WeblogEntry entry) {
        return render(entry, entry.getSummary());
    }

    /**
     * Get the right transformed display content depending on the situation.
     */
    public static String displayContent(WeblogEntry entry, String readMoreLink) {
        String displayContent;
        if (readMoreLink == null || readMoreLink.isBlank() || "nil".equals(readMoreLink)) {
            // no readMore link means permalink, so prefer text over summary
            if (StringUtils.isNotEmpty(entry.getText())) {
                displayContent = getTransformedText(entry);
            } else {
                displayContent = getTransformedSummary(entry);
            }
        } else {
            // not a permalink, so prefer summary over text
            // include a "read more" link if needed
            if (StringUtils.isNotEmpty(entry.getSummary())) {
                displayContent = getTransformedSummary(entry);
                if (StringUtils.isNotEmpty(entry.getText())) {
                    // add read more
                    List<String> args = List.of(readMoreLink);
                    String readMore = I18nMessages.getMessages(entry.getWebsite().getLocaleInstance()).getString("macro.weblog.readMoreLink", args);
                    displayContent += readMore;
                }
            } else {
                displayContent = getTransformedText(entry);
            }
        }
        return HTMLSanitizer.conditionallySanitize(displayContent);
    }
}
