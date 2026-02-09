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
import java.util.Collections;
import java.util.Comparator;
import java.util.Date;
import java.util.List;
import jakarta.persistence.NoResultException;
import jakarta.persistence.Query;
import jakarta.persistence.TypedQuery;

import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;
import org.apache.roller.weblogger.WebloggerException;
import org.apache.roller.weblogger.business.TagManager;
import org.apache.roller.weblogger.business.Weblogger;
import org.apache.roller.weblogger.pojos.TagStat;
import org.apache.roller.weblogger.pojos.TagStatComparator;
import org.apache.roller.weblogger.pojos.TagStatCountComparator;
import org.apache.roller.weblogger.pojos.Weblog;
import org.apache.roller.weblogger.pojos.WeblogEntryTagAggregate;

/**
 * JPA implementation of TagManager.
 * Extracted from JPAWeblogEntryManagerImpl as part of God Class refactoring.
 * 
 * Handles all tag-related operations including tag queries,
 * statistics, and aggregations.
 */
@com.google.inject.Singleton
public class JPATagManagerImpl implements TagManager {

    private static final Log LOG = LogFactory.getLog(JPATagManagerImpl.class);

    private final Weblogger roller;
    private final JPAPersistenceStrategy strategy;

    private static final Comparator<TagStat> TAG_STAT_NAME_COMPARATOR = new TagStatComparator();
    private static final Comparator<TagStat> TAG_STAT_COUNT_REVERSE_COMPARATOR =
            Collections.reverseOrder(TagStatCountComparator.getInstance());

    @com.google.inject.Inject
    protected JPATagManagerImpl(Weblogger roller, JPAPersistenceStrategy strategy) {
        LOG.debug("Instantiating JPA Tag Manager");
        this.roller = roller;
        this.strategy = strategy;
    }

    @Override
    public List<TagStat> getPopularTags(Weblog website, Date startDate, int offset, int limit)
            throws WebloggerException {
        TypedQuery<TagStat> query;
        List<TagStat> queryResults;
        
        if (website != null) {
            if (startDate != null) {
                Timestamp start = new Timestamp(startDate.getTime());
                query = strategy.getNamedQuery(
                        "WeblogEntryTagAggregate.getPopularTagsByWebsite&StartDate", TagStat.class);
                query.setParameter(1, website);
                query.setParameter(2, start);
            } else {
                query = strategy.getNamedQuery(
                        "WeblogEntryTagAggregate.getPopularTagsByWebsite", TagStat.class);
                query.setParameter(1, website);
            }
        } else {
            if (startDate != null) {
                Timestamp start = new Timestamp(startDate.getTime());
                query = strategy.getNamedQuery(
                        "WeblogEntryTagAggregate.getPopularTagsByWebsiteNull&StartDate", TagStat.class);
                query.setParameter(1, start);
            } else {
                query = strategy.getNamedQuery(
                        "WeblogEntryTagAggregate.getPopularTagsByWebsiteNull", TagStat.class);
            }
        }
        setFirstMax(query, offset, limit);
        queryResults = query.getResultList();
        
        double min = Integer.MAX_VALUE;
        double max = Integer.MIN_VALUE;
        
        List<TagStat> results = new ArrayList<>(limit >= 0 ? limit : 25);
        
        if (queryResults != null) {
            for (Object obj : queryResults) {
                Object[] row = (Object[]) obj;
                TagStat t = new TagStat();
                t.setName((String) row[0]);
                t.setCount(((Number) row[1]).intValue());

                min = Math.min(min, t.getCount());
                max = Math.max(max, t.getCount());
                results.add(t);
            }
        }

        min = Math.log(1+min);
        max = Math.log(1+max);
        
        double range = Math.max(.01, max - min) * 1.0001;
        
        for (TagStat t : results) {
            t.setIntensity((int) (1 + Math.floor(5 * (Math.log(1+t.getCount()) - min) / range)));
        }

        // sort results by name, because query had to sort by total
        results.sort(TAG_STAT_NAME_COMPARATOR);
        
        return results;
    }

    @Override
    public List<TagStat> getTags(Weblog website, String sortBy, String startsWith, 
            int offset, int limit) throws WebloggerException {
        Query query;
        List<?> queryResults;
        boolean sortByName = sortBy == null || !sortBy.equals("count");
                
        List<Object> params = new ArrayList<>();
        int size = 0;
        StringBuilder queryString = new StringBuilder();
        queryString.append("SELECT w.name, SUM(w.total) FROM WeblogEntryTagAggregate w WHERE ");
                
        if (website != null) {
            params.add(size++, website.getId());
            queryString.append(" w.weblog.id = ?").append(size);
        } else {
            queryString.append(" w.weblog IS NULL"); 
        }
                       
        if (startsWith != null && startsWith.length() > 0) {
            params.add(size++, startsWith + '%');
            queryString.append(" AND w.name LIKE ?").append(size);
        }
                    
        if (sortBy != null && sortBy.equals("count")) {
            sortBy = "w.total DESC";
        } else {
            sortBy = "w.name";
        }
        queryString.append(" GROUP BY w.name, w.total ORDER BY ").append(sortBy);

        query = strategy.getDynamicQuery(queryString.toString());
        for (int i=0; i<params.size(); i++) {
            query.setParameter(i+1, params.get(i));
        }
        setFirstMax(query, offset, limit);
        queryResults = query.getResultList();
        
        List<TagStat> results = new ArrayList<>();
        if (queryResults != null) {
            for (Object obj : queryResults) {
                Object[] row = (Object[]) obj;
                TagStat ce = new TagStat();
                ce.setName((String) row[0]);
                ce.setCount(((Long) row[1]).intValue());
                results.add(ce);
            }
        }

        if (sortByName) {
            results.sort(TAG_STAT_NAME_COMPARATOR);
        } else {
            results.sort(TAG_STAT_COUNT_REVERSE_COMPARATOR);
        }
        
        return results;
    }

    @Override
    public boolean getTagComboExists(List<String> tags, Weblog weblog) throws WebloggerException {
        if (tags == null || tags.isEmpty()) {
            return false;
        }
        
        StringBuilder queryString = new StringBuilder();
        queryString.append("SELECT DISTINCT w.name ");
        queryString.append("FROM WeblogEntryTagAggregate w WHERE w.name IN (");
        List<Object> params = new ArrayList<>(tags.size() + 1);
        final String paramSeparator = ", ";
        int i;
        for (i=0; i < tags.size(); i++) {
            queryString.append('?').append(i+1).append(paramSeparator);
            params.add(tags.get(i));
        }
        
        queryString.delete(queryString.length() - paramSeparator.length(),
                queryString.length());
        queryString.append(')');
        
        if(weblog != null) {
            queryString.append(" AND w.weblog = ?").append(i+1);
            params.add(weblog);
        } else {
            queryString.append(" AND w.weblog IS NULL");
        }
        
        TypedQuery<String> q = strategy.getDynamicQuery(queryString.toString(), String.class);
        for (int j=0; j<params.size(); j++) {
            q.setParameter(j+1, params.get(j));
        }
        
        List<String> results = q.getResultList();
        return (results != null && results.size() == tags.size());
    }

    /**
     * Updates tag aggregate counts. Called internally when entries are saved/deleted.
     * 
     * @param name The tag name
     * @param website The website to update
     * @param amount The amount to increment (positive or negative)
     * @throws WebloggerException if there is an error
     */
    public void updateTagCount(String name, Weblog website, int amount)
            throws WebloggerException {
        if (amount == 0) {
            throw new WebloggerException("Tag increment amount cannot be zero.");
        }
        
        if (website == null) {
            throw new WebloggerException("Website cannot be NULL.");
        }
        
        TypedQuery<WeblogEntryTagAggregate> weblogQuery = strategy.getNamedQuery(
                "WeblogEntryTagAggregate.getByName&WebsiteOrderByLastUsedDesc", WeblogEntryTagAggregate.class);
        weblogQuery.setParameter(1, name);
        weblogQuery.setParameter(2, website);
        WeblogEntryTagAggregate weblogTagData;
        try {
            weblogTagData = weblogQuery.getSingleResult();
        } catch (NoResultException e) {
            weblogTagData = null;
        }

        TypedQuery<WeblogEntryTagAggregate> siteQuery = strategy.getNamedQuery(
                "WeblogEntryTagAggregate.getByName&WebsiteNullOrderByLastUsedDesc", WeblogEntryTagAggregate.class);
        siteQuery.setParameter(1, name);
        WeblogEntryTagAggregate siteTagData;
        try {
            siteTagData = siteQuery.getSingleResult();
        } catch (NoResultException e) {
            siteTagData = null;
        }
        Timestamp lastUsed = new Timestamp((new Date()).getTime());
        
        if (weblogTagData == null && amount > 0) {
            weblogTagData = new WeblogEntryTagAggregate(null, website, name, amount);
            weblogTagData.setLastUsed(lastUsed);
            strategy.store(weblogTagData);
        } else if (weblogTagData != null) {
            weblogTagData.setTotal(weblogTagData.getTotal() + amount);
            weblogTagData.setLastUsed(lastUsed);
            strategy.store(weblogTagData);
        }
        
        if (siteTagData == null && amount > 0) {
            siteTagData = new WeblogEntryTagAggregate(null, null, name, amount);
            siteTagData.setLastUsed(lastUsed);
            strategy.store(siteTagData);
        } else if (siteTagData != null) {
            siteTagData.setTotal(siteTagData.getTotal() + amount);
            siteTagData.setLastUsed(lastUsed);
            strategy.store(siteTagData);
        }
        
        Query removeq = strategy.getNamedUpdate(
                "WeblogEntryTagAggregate.removeByTotalLessEqual");
        removeq.setParameter(1, 0);
        removeq.executeUpdate();
    }

    @Override
    public void release() {
        // No resources to release
    }

    private static void setFirstMax(Query query, int offset, int length) {
        if (offset != 0) {
            query.setFirstResult(offset);
        }
        if (length != -1) {
            query.setMaxResults(length);
        }
    }
}
