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

import java.util.List;
import jakarta.persistence.NoResultException;
import jakarta.persistence.TypedQuery;

import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;
import org.apache.roller.weblogger.WebloggerException;
import org.apache.roller.weblogger.business.CategoryManager;
import org.apache.roller.weblogger.business.Weblogger;
import org.apache.roller.weblogger.pojos.Weblog;
import org.apache.roller.weblogger.pojos.WeblogCategory;
import org.apache.roller.weblogger.pojos.WeblogEntry;

/**
 * JPA implementation of CategoryManager.
 * Extracted from JPAWeblogEntryManagerImpl as part of God Class refactoring.
 * 
 * Handles all category-related operations including CRUD
 * and category content management.
 */
@com.google.inject.Singleton
public class JPACategoryManagerImpl implements CategoryManager {

    private static final Log LOG = LogFactory.getLog(JPACategoryManagerImpl.class);

    private final Weblogger roller;
    private final JPAPersistenceStrategy strategy;

    @com.google.inject.Inject
    protected JPACategoryManagerImpl(Weblogger roller, JPAPersistenceStrategy strategy) {
        LOG.debug("Instantiating JPA Category Manager");
        this.roller = roller;
        this.strategy = strategy;
    }

    @Override
    public void saveWeblogCategory(WeblogCategory cat) throws WebloggerException {
        boolean exists = getWeblogCategory(cat.getId()) != null;
        if (!exists && isDuplicateWeblogCategoryName(cat)) {
            throw new WebloggerException("Duplicate category name, cannot save category");
        }

        // update weblog last modified date
        roller.getWeblogManager().saveWeblog(cat.getWeblog());
        
        this.strategy.store(cat);
    }

    @Override
    public void removeWeblogCategory(WeblogCategory cat) throws WebloggerException {
        if(!cat.retrieveWeblogEntries(false).isEmpty()) {
            throw new WebloggerException("Cannot remove category with entries");
        }

        cat.getWeblog().getWeblogCategories().remove(cat);

        // remove cat
        this.strategy.remove(cat);

        if(cat.equals(cat.getWeblog().getBloggerCategory())) {
            cat.getWeblog().setBloggerCategory(null);
            this.strategy.store(cat.getWeblog());
        }

        // update weblog last modified date
        roller.getWeblogManager().saveWeblog(cat.getWeblog());
    }

    @Override
    public void moveWeblogCategoryContents(WeblogCategory srcCat, WeblogCategory destCat)
            throws WebloggerException {
        
        // get all entries in category and subcats
        List<WeblogEntry> results = srcCat.retrieveWeblogEntries(false);
        
        // Loop through entries in src cat, assign them to dest cat
        Weblog website = destCat.getWeblog();
        for (WeblogEntry entry : results) {
            entry.setCategory(destCat);
            entry.setWebsite(website);
            this.strategy.store(entry);
        }
        
        // Update Blogger API category if applicable
        WeblogCategory bloggerCategory = srcCat.getWeblog().getBloggerCategory();
        if (bloggerCategory != null && bloggerCategory.getId().equals(srcCat.getId())) {
            srcCat.getWeblog().setBloggerCategory(destCat);
            this.strategy.store(srcCat.getWeblog());
        }
    }

    @Override
    public WeblogCategory getWeblogCategory(String id) throws WebloggerException {
        return (WeblogCategory) this.strategy.load(WeblogCategory.class, id);
    }

    @Override
    public WeblogCategory getWeblogCategoryByName(Weblog weblog, String categoryName) 
            throws WebloggerException {
        TypedQuery<WeblogCategory> q = strategy.getNamedQuery(
                "WeblogCategory.getByWeblog&Name", WeblogCategory.class);
        q.setParameter(1, weblog);
        q.setParameter(2, categoryName);
        try {
            return q.getSingleResult();
        } catch (NoResultException e) {
            return null;
        }
    }

    @Override
    public List<WeblogCategory> getWeblogCategories(Weblog website) throws WebloggerException {
        TypedQuery<WeblogCategory> q = strategy.getNamedQuery(
                "WeblogCategory.getByWebsite", WeblogCategory.class);
        q.setParameter(1, website);
        return q.getResultList();
    }

    @Override
    public boolean isDuplicateWeblogCategoryName(WeblogCategory cat) throws WebloggerException {
        return (getWeblogCategoryByName(cat.getWeblog(), cat.getName()) != null);
    }

    @Override
    public boolean isWeblogCategoryInUse(WeblogCategory cat) throws WebloggerException {
        if (cat.getWeblog().getBloggerCategory().equals(cat)) {
            return true;
        }
        TypedQuery<WeblogEntry> q = strategy.getNamedQuery("WeblogEntry.getByCategory", WeblogEntry.class);
        q.setParameter(1, cat);
        int entryCount = q.getResultList().size();
        return entryCount > 0;
    }

    @Override
    public void release() {
        // No resources to release
    }
}
