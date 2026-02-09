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

package org.apache.roller.weblogger.business.jpa;

import java.sql.Timestamp;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import jakarta.persistence.TypedQuery;

import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;
import org.apache.roller.weblogger.WebloggerException;
import org.apache.roller.weblogger.business.CommentManager;
import org.apache.roller.weblogger.business.Weblogger;
import org.apache.roller.weblogger.pojos.CommentSearchCriteria;
import org.apache.roller.weblogger.pojos.Weblog;
import org.apache.roller.weblogger.pojos.WeblogEntry;
import org.apache.roller.weblogger.pojos.WeblogEntryComment;
import org.apache.roller.weblogger.pojos.WeblogEntryComment.ApprovalStatus;

/**
 * JPA implementation of CommentManager.
 * Extracted from JPAWeblogEntryManagerImpl as part of God Class refactoring.
 * 
 * Handles all comment-related operations including CRUD,
 * bulk operations, and queries.
 */
@com.google.inject.Singleton
public class JPACommentManagerImpl implements CommentManager {

    private static final Log LOG = LogFactory.getLog(JPACommentManagerImpl.class);

    private final Weblogger roller;
    private final JPAPersistenceStrategy strategy;

    @com.google.inject.Inject
    protected JPACommentManagerImpl(Weblogger roller, JPAPersistenceStrategy strategy) {
        LOG.debug("Instantiating JPA Comment Manager");
        this.roller = roller;
        this.strategy = strategy;
    }

    @Override
    public void saveComment(WeblogEntryComment comment) throws WebloggerException {
        this.strategy.store(comment);
        
        // update weblog last modified date
        roller.getWeblogManager().saveWeblog(comment.getWeblogEntry().getWebsite());
    }

    @Override
    public void removeComment(WeblogEntryComment comment) throws WebloggerException {
        this.strategy.remove(comment);
        
        // update weblog last modified date
        roller.getWeblogManager().saveWeblog(comment.getWeblogEntry().getWebsite());
    }

    @Override
    public WeblogEntryComment getComment(String id) throws WebloggerException {
        return (WeblogEntryComment) this.strategy.load(WeblogEntryComment.class, id);
    }

    @Override
    public List<WeblogEntryComment> getComments(CommentSearchCriteria csc) throws WebloggerException {
        List<Object> params = new ArrayList<>();
        int size = 0;
        StringBuilder queryString = new StringBuilder();
        queryString.append("SELECT c FROM WeblogEntryComment c ");
        
        StringBuilder whereClause = new StringBuilder();
        if (csc.getEntry() != null) {
            params.add(size++, csc.getEntry());
            whereClause.append("c.weblogEntry = ?").append(size);
        } else if (csc.getWeblog() != null) {
            params.add(size++, csc.getWeblog());
            whereClause.append("c.weblogEntry.website = ?").append(size);
        }
        
        if (csc.getSearchText() != null) {
            params.add(size++, "%" + csc.getSearchText().toUpperCase() + "%");
            appendConjuctionToWhereclause(whereClause, "upper(c.content) LIKE ?").append(size);
        }
        
        if (csc.getStartDate() != null) {
            Timestamp start = new Timestamp(csc.getStartDate().getTime());
            params.add(size++, start);
            appendConjuctionToWhereclause(whereClause, "c.postTime >= ?").append(size);
        }
        
        if (csc.getEndDate() != null) {
            Timestamp end = new Timestamp(csc.getEndDate().getTime());
            params.add(size++, end);
            appendConjuctionToWhereclause(whereClause, "c.postTime <= ?").append(size);
        }
        
        if (csc.getStatus() != null) {
            params.add(size++, csc.getStatus());
            appendConjuctionToWhereclause(whereClause, "c.status = ?").append(size);
        }
        
        if(whereClause.length() != 0) {
            queryString.append(" WHERE ").append(whereClause);
        }
        if (csc.isReverseChrono()) {
            queryString.append(" ORDER BY c.postTime DESC");
        } else {
            queryString.append(" ORDER BY c.postTime ASC");
        }
        
        TypedQuery<WeblogEntryComment> query = strategy.getDynamicQuery(queryString.toString(), WeblogEntryComment.class);
        setFirstMax( query, csc.getOffset(), csc.getMaxResults());
        for (int i=0; i<params.size(); i++) {
            query.setParameter(i+1, params.get(i));
        }
        return query.getResultList();
    }

    @Override
    public int removeMatchingComments(
            Weblog weblog,
            WeblogEntry entry,
            String searchString,
            Date startDate,
            Date endDate,
            ApprovalStatus status) throws WebloggerException {
        
        CommentSearchCriteria csc = new CommentSearchCriteria();
        csc.setWeblog(weblog);
        csc.setEntry(entry);
        csc.setSearchText(searchString);
        csc.setStartDate(startDate);
        csc.setEndDate(endDate);
        csc.setStatus(status);

        List<WeblogEntryComment> comments = getComments(csc);
        int count = 0;
        for (WeblogEntryComment comment : comments) {
            removeComment(comment);
            count++;
        }
        return count;
    }

    @Override
    public long getCommentCount() throws WebloggerException {
        TypedQuery<Long> q = strategy.getNamedQuery(
                "WeblogEntryComment.getCountAllDistinctByStatus", Long.class);
        q.setParameter(1, ApprovalStatus.APPROVED);
        return q.getResultList().get(0);
    }

    @Override
    public long getCommentCount(Weblog website) throws WebloggerException {
        TypedQuery<Long> q = strategy.getNamedQuery(
                "WeblogEntryComment.getCountDistinctByWebsite&Status", Long.class);
        q.setParameter(1, website);
        q.setParameter(2, ApprovalStatus.APPROVED);
        return q.getResultList().get(0);
    }

    @Override
    public void applyCommentDefaultsToEntries(Weblog website) throws WebloggerException {
        if (LOG.isDebugEnabled()) {
            LOG.debug("applyCommentDefaults");
        }
        
        jakarta.persistence.Query q = strategy.getNamedUpdate(
                "WeblogEntry.updateAllowComments&CommentDaysByWebsite");
        q.setParameter(1, website.getDefaultAllowComments());
        q.setParameter(2, website.getDefaultCommentDays());
        q.setParameter(3, website);
        q.executeUpdate();
    }

    @Override
    public void release() {
        // No resources to release
    }

    private static void setFirstMax(jakarta.persistence.Query query, int offset, int length) {
        if (offset != 0) {
            query.setFirstResult(offset);
        }
        if (length != -1) {
            query.setMaxResults(length);
        }
    }

    private static StringBuilder appendConjuctionToWhereclause(StringBuilder whereClause, String expression) {
        if (whereClause.length() != 0 && expression.length() != 0) {
            whereClause.append(" AND ");
        }
        return whereClause.append(expression);
    }
}
