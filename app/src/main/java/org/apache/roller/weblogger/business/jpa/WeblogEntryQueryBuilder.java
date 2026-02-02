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

package org.apache.roller.weblogger.business.jpa;

import org.apache.commons.lang3.StringUtils;
import org.apache.roller.weblogger.pojos.WeblogCategory;
import org.apache.roller.weblogger.pojos.WeblogEntrySearchCriteria;

import java.sql.Timestamp;
import java.util.ArrayList;
import java.util.List;

/**
 * Builder class for constructing JPQL queries for WeblogEntry searches.
 * Extracts the complex query building logic from JPAWeblogEntryManagerImpl
 * to improve maintainability and testability.
 */
public class WeblogEntryQueryBuilder {
    
    private final WeblogEntrySearchCriteria criteria;
    private final StringBuilder queryString;
    private final List<Object> params;
    private WeblogCategory category;
    private boolean whereClauseStarted;
    
    private WeblogEntryQueryBuilder(WeblogEntrySearchCriteria criteria) {
        this.criteria = criteria;
        this.queryString = new StringBuilder();
        this.params = new ArrayList<>();
        this.whereClauseStarted = false;
    }
    
    /**
     * Creates a new query builder for the given search criteria.
     * 
     * @param criteria the search criteria
     * @return a new query builder instance
     */
    public static WeblogEntryQueryBuilder forCriteria(WeblogEntrySearchCriteria criteria) {
        return new WeblogEntryQueryBuilder(criteria);
    }
    
    /**
     * Sets the category for the query (resolved externally).
     * 
     * @param category the weblog category, may be null
     * @return this builder for method chaining
     */
    public WeblogEntryQueryBuilder withCategory(WeblogCategory category) {
        this.category = category;
        return this;
    }
    
    /**
     * Builds the JPQL query string based on the search criteria.
     * 
     * @return the complete JPQL query string
     */
    public String buildQuery() {
        appendSelectClause();
        appendTagsCondition();
        appendWeblogCondition();
        appendUserCondition();
        appendDateRangeConditions();
        appendCategoryCondition();
        appendStatusCondition();
        appendLocaleCondition();
        appendTextSearchCondition();
        appendOrderByClause();
        return queryString.toString();
    }
    
    /**
     * Gets the list of parameters to be set on the query.
     * 
     * @return list of parameter values in order
     */
    public List<Object> getParameters() {
        return params;
    }
    
    private void appendSelectClause() {
        if (criteria.getTags() == null || criteria.getTags().isEmpty()) {
            queryString.append("SELECT e FROM WeblogEntry e WHERE ");
        } else {
            queryString.append("SELECT e FROM WeblogEntry e JOIN e.tags t WHERE ");
        }
        whereClauseStarted = true;
    }
    
    private void appendTagsCondition() {
        if (criteria.getTags() != null && !criteria.getTags().isEmpty()) {
            queryString.append("(");
            for (int i = 0; i < criteria.getTags().size(); i++) {
                if (i != 0) {
                    queryString.append(" OR ");
                }
                params.add(criteria.getTags().get(i));
                queryString.append(" t.name = ?").append(params.size());
            }
            queryString.append(") AND ");
        }
    }

    private void appendWeblogCondition() {
        if (criteria.getWeblog() != null) {
            params.add(criteria.getWeblog().getId());
            queryString.append("e.website.id = ?").append(params.size());
        } else {
            params.add(Boolean.TRUE);
            queryString.append("e.website.visible = ?").append(params.size());
        }
    }

    private void appendUserCondition() {
        if (criteria.getUser() != null) {
            params.add(criteria.getUser().getUserName());
            queryString.append(" AND e.creatorUserName = ?").append(params.size());
        }
    }

    private void appendDateRangeConditions() {
        if (criteria.getStartDate() != null) {
            Timestamp start = new Timestamp(criteria.getStartDate().getTime());
            params.add(start);
            queryString.append(" AND e.pubTime >= ?").append(params.size());
        }

        if (criteria.getEndDate() != null) {
            Timestamp end = new Timestamp(criteria.getEndDate().getTime());
            params.add(end);
            queryString.append(" AND e.pubTime <= ?").append(params.size());
        }
    }

    private void appendCategoryCondition() {
        if (category != null) {
            params.add(category.getId());
            queryString.append(" AND e.category.id = ?").append(params.size());
        }
    }

    private void appendStatusCondition() {
        if (criteria.getStatus() != null) {
            params.add(criteria.getStatus());
            queryString.append(" AND e.status = ?").append(params.size());
        }
    }

    private void appendLocaleCondition() {
        if (criteria.getLocale() != null) {
            params.add(criteria.getLocale() + '%');
            queryString.append(" AND e.locale like ?").append(params.size());
        }
    }

    private void appendTextSearchCondition() {
        if (StringUtils.isNotEmpty(criteria.getText())) {
            params.add('%' + criteria.getText() + '%');
            queryString.append(" AND ( e.text LIKE ?").append(params.size());
            queryString.append("    OR e.summary LIKE ?").append(params.size());
            queryString.append("    OR e.title LIKE ?").append(params.size());
            queryString.append(") ");
        }
    }
    
    private void appendOrderByClause() {
        if (criteria.getSortBy() != null && 
            criteria.getSortBy().equals(WeblogEntrySearchCriteria.SortBy.UPDATE_TIME)) {
            queryString.append(" ORDER BY e.updateTime ");
        } else {
            queryString.append(" ORDER BY e.pubTime ");
        }
        
        if (criteria.getSortOrder() != null && 
            criteria.getSortOrder().equals(WeblogEntrySearchCriteria.SortOrder.ASCENDING)) {
            queryString.append("ASC ");
        } else {
            queryString.append("DESC ");
        }
    }
}
