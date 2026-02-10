/*
 * Licensed to the Apache Software Foundation (ASF) under one or more
 *  contributor license agreements.  The ASF licenses this file to You
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

/* Created on Jul 16, 2003 */

package org.apache.roller.weblogger.business.search.lucene;

import java.io.IOException;
import java.util.List;

import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;

/**
 * This is the base class for all index operation. These operations include:<br>
 * SearchOperation<br>
 * AddEntryOperation<br>
 * RemoveEntryOperation<br>
 * ReIndexEntryOperation<br>
 * RemoveWebsiteIndexOperation<br>
 * RebuildWebsiteIndexOperation
 * 
 * @author Mindaugas Idzelis (min@idzelis.com)
 */
public abstract class IndexOperation implements Runnable {

    private static Log logger = LogFactory.getFactory().getInstance(
            IndexOperation.class);

    // ~ Instance fields
    // ========================================================
    protected LuceneIndexManager manager;

    // ~ Constructors
    // ===========================================================
    public IndexOperation(LuceneIndexManager manager) {
        this.manager = manager;
    }

    // ~ Methods
    // ================================================================

    /**
     * @see java.lang.Runnable#run()
     */
    @Override
    public void run() {
        doRun();
    }

    protected abstract void doRun();
}
