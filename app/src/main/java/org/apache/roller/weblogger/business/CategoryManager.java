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
import org.apache.roller.weblogger.pojos.WeblogCategory;

/**
 * Interface for managing weblog categories.
 * Extracted from WeblogEntryManager as part of the God Class refactoring.
 * 
 * This interface handles all category-related operations including
 * CRUD operations and category content management.
 */
public interface CategoryManager {

    /**
     * Save weblog category.
     * @param cat Category to save
     * @throws WebloggerException if there is an error
     */
    void saveWeblogCategory(WeblogCategory cat) throws WebloggerException;

    /**
     * Remove weblog category.
     * @param cat Category to remove
     * @throws WebloggerException if there is an error
     */
    void removeWeblogCategory(WeblogCategory cat) throws WebloggerException;

    /**
     * Get category by id.
     * @param id Category ID
     * @return The category or null if not found
     * @throws WebloggerException if there is an error
     */
    WeblogCategory getWeblogCategory(String id) throws WebloggerException;

    /**
     * Recategorize all entries with one category to another.
     * @param srcCat Source category
     * @param destCat Destination category
     * @throws WebloggerException if there is an error
     */
    void moveWeblogCategoryContents(WeblogCategory srcCat, WeblogCategory destCat)
            throws WebloggerException;

    /**
     * Get category specified by website and name.
     * @param website Website of WeblogCategory
     * @param categoryName Name of WeblogCategory
     * @return The category or null if not found
     * @throws WebloggerException if there is an error
     */
    WeblogCategory getWeblogCategoryByName(Weblog website, String categoryName)
            throws WebloggerException;

    /**
     * Get WebLogCategory objects for a website.
     * @param website The weblog
     * @return List of categories
     * @throws WebloggerException if there is an error
     */
    List<WeblogCategory> getWeblogCategories(Weblog website)
            throws WebloggerException;

    /**
     * Check for duplicate category name.
     * @param data Category to check
     * @return true if duplicate exists
     * @throws WebloggerException if there is an error
     */
    boolean isDuplicateWeblogCategoryName(WeblogCategory data)
            throws WebloggerException;

    /**
     * Check if weblog category is in use.
     * @param data Category to check
     * @return true if category has entries
     * @throws WebloggerException if there is an error
     */
    boolean isWeblogCategoryInUse(WeblogCategory data)
            throws WebloggerException;

    /**
     * Release all resources held by manager.
     */
    void release();
}
