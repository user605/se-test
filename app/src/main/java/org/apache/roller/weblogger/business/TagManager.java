/*
 * Licensed to the Apache Software Foundation (ASF) under one or more
 * contributor license agreements. The ASF licenses this file to You
 * under the Apache License, Version 2.0 (the "License"); you may not
 * use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package org.apache.roller.weblogger.business;

import java.util.Date;
import java.util.List;
import org.apache.roller.weblogger.WebloggerException;
import org.apache.roller.weblogger.pojos.TagStat;
import org.apache.roller.weblogger.pojos.Weblog;

/**
 * Interface for managing weblog entry tags.
 * Extracted from WeblogEntryManager as part of the God Class refactoring.
 * 
 * This interface handles all tag-related operations including
 * tag queries, statistics, and aggregations.
 */
public interface TagManager {

    /**
     * Get list of TagStat for most popular tags.
     * @param website Weblog or null to get for all weblogs
     * @param startDate Date or null of the most recent time a tag was used
     * @param offset Offset into results for paging
     * @param limit Max TagStats to return (or -1 for no limit)
     * @return List of most popular tags
     * @throws WebloggerException if there is an error
     */
    List<TagStat> getPopularTags(Weblog website, Date startDate, int offset, int limit)
            throws WebloggerException;

    /**
     * Get list of TagStat with filtering and sorting options.
     * @param website Weblog or null to get for all weblogs
     * @param sortBy Sort by either 'name' or 'count' (null for name)
     * @param startsWith Prefix for tags to be returned (null or a string of length > 0)
     * @param offset Offset into results for paging
     * @param limit Max TagStats to return (or -1 for no limit)
     * @return List of tags matching the criteria
     * @throws WebloggerException if there is an error
     */
    List<TagStat> getTags(Weblog website, String sortBy, String startsWith, int offset, int limit)
            throws WebloggerException;

    /**
     * Does the specified tag combination exist? Optionally confined to a specific weblog.
     * @param tags The List of tags to check for
     * @param weblog The weblog to confine the check to
     * @return True if tags exist, false otherwise
     * @throws WebloggerException if there is an error
     */
    boolean getTagComboExists(List<String> tags, Weblog weblog) throws WebloggerException;

    /**
     * Release all resources held by manager.
     */
    void release();
}
