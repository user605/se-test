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

import java.util.List;
import org.apache.roller.weblogger.WebloggerException;
import org.apache.roller.weblogger.pojos.Weblog;
import org.apache.roller.weblogger.pojos.WeblogHitCount;

/**
 * Interface for managing weblog hit counts.
 * Extracted from WeblogEntryManager as part of the God Class refactoring.
 * 
 * This interface handles all hit count related operations including
 * CRUD operations, incrementing, and retrieving hot weblogs.
 */
public interface HitCountManager {

    /**
     * Get a HitCountData by id.
     * @param id The HitCountData id
     * @return The HitCountData object, or null if it wasn't found
     * @throws WebloggerException if there is an error
     */
    WeblogHitCount getHitCount(String id) throws WebloggerException;

    /**
     * Get a HitCountData by weblog.
     * @param weblog The WebsiteData that you want the hit count for
     * @return The HitCountData object, or null if it wasn't found
     * @throws WebloggerException if there is an error
     */
    WeblogHitCount getHitCountByWeblog(Weblog weblog)
            throws WebloggerException;

    /**
     * Get HitCountData objects for the hottest weblogs.
     * @param sinceDays Number of days in the past to consider
     * @param offset What index in the results to begin from
     * @param length The number of results to return
     * @return The list of HitCountData objects ranked by hit count, descending
     * @throws WebloggerException if there is an error
     */
    List<WeblogHitCount> getHotWeblogs(int sinceDays, int offset, int length)
            throws WebloggerException;

    /**
     * Save a HitCountData object.
     * @param hitCount The HitCountData object to save
     * @throws WebloggerException if there is an error
     */
    void saveHitCount(WeblogHitCount hitCount) throws WebloggerException;

    /**
     * Remove a HitCountData object.
     * @param hitCount The HitCountData object to remove
     * @throws WebloggerException if there is an error
     */
    void removeHitCount(WeblogHitCount hitCount) throws WebloggerException;

    /**
     * Increment the hit count for a weblog by a certain amount.
     * @param weblog The WebsiteData object to increment the count for
     * @param amount How much to increment by
     * @throws WebloggerException if there is an error
     */
    void incrementHitCount(Weblog weblog, int amount)
            throws WebloggerException;

    /**
     * Reset the hit counts for all weblogs. This sets the counts back to 0.
     * @throws WebloggerException if there is an error
     */
    void resetAllHitCounts() throws WebloggerException;

    /**
     * Reset the hit counts for a single weblog. This sets the count to 0.
     * @param weblog The WebsiteData object to reset the count for
     * @throws WebloggerException if there is an error
     */
    void resetHitCount(Weblog weblog) throws WebloggerException;

    /**
     * Release all resources held by manager.
     */
    void release();
}
