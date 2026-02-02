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
import org.apache.roller.weblogger.pojos.CommentSearchCriteria;
import org.apache.roller.weblogger.pojos.Weblog;
import org.apache.roller.weblogger.pojos.WeblogEntry;
import org.apache.roller.weblogger.pojos.WeblogEntryComment;
import org.apache.roller.weblogger.pojos.WeblogEntryComment.ApprovalStatus;

/**
 * Interface for managing weblog entry comments.
 * Extracted from WeblogEntryManager as part of the God Class refactoring.
 * 
 * This interface handles all comment-related operations including
 * CRUD operations, bulk operations, and queries.
 */
public interface CommentManager {

    /**
     * Save comment.
     * @param comment Comment to save
     * @throws WebloggerException if there is an error
     */
    void saveComment(WeblogEntryComment comment) throws WebloggerException;

    /**
     * Remove comment.
     * @param comment Comment to remove
     * @throws WebloggerException if there is an error
     */
    void removeComment(WeblogEntryComment comment) throws WebloggerException;

    /**
     * Get comment by id.
     * @param id Comment ID
     * @return The comment or null if not found
     * @throws WebloggerException if there is an error
     */
    WeblogEntryComment getComment(String id) throws WebloggerException;

    /**
     * Generic comments query method.
     * @param csc CommentSearchCriteria object with fields indicating search criteria
     * @return list of comments fitting search criteria
     * @throws WebloggerException if there is an error
     */
    List<WeblogEntryComment> getComments(CommentSearchCriteria csc) throws WebloggerException;

    /**
     * Deletes comments that match parameters.
     * @param website Weblog or null for all comments on site
     * @param entry Entry or null to include all comments
     * @param searchString Search string for comment content
     * @param startDate Start date or null for no restriction
     * @param endDate End date or null for no restriction
     * @param status Status of comment
     * @return Number of comments deleted
     * @throws WebloggerException if there is an error
     */
    int removeMatchingComments(
            Weblog website,
            WeblogEntry entry,
            String searchString,
            Date startDate,
            Date endDate,
            ApprovalStatus status
    ) throws WebloggerException;

    /**
     * Get site-wide comment count.
     * @return Total number of comments
     * @throws WebloggerException if there is an error
     */
    long getCommentCount() throws WebloggerException;

    /**
     * Get weblog comment count.
     * @param website The weblog
     * @return Number of comments for the weblog
     * @throws WebloggerException if there is an error
     */
    long getCommentCount(Weblog website) throws WebloggerException;

    /**
     * Apply comment default settings from website to all of website's entries.
     * @param website The weblog
     * @throws WebloggerException if there is an error
     */
    void applyCommentDefaultsToEntries(Weblog website) throws WebloggerException;

    /**
     * Release all resources held by manager.
     */
    void release();
}
