# Search and Filtering System Documentation

## Overview

The Todo API implements a comprehensive search and filtering system that allows users to efficiently find and organize their tasks. The system provides full-text search, advanced filtering options, sorting capabilities, and performance optimizations through caching.

## Features

### Core Search Capabilities
- **Full-Text Search** in task titles and descriptions
- **Multi-keyword Search** with automatic keyword extraction
- **Quoted Phrase Search** for exact phrase matching
- **Case-Insensitive Search** for better user experience
- **Performance Optimized** with result caching

### Advanced Filtering
- **Priority Filtering** (low, medium, high)
- **Completion Status** filtering (completed/incomplete)
- **Date Range Filtering** for due dates and creation dates
- **Multi-Value Filters** (e.g., multiple priorities)
- **User Scope** (admin can see all tasks, users see only their own)

### Sorting & Pagination
- **Flexible Sorting** by title, priority, dates, completion status
- **Ascending/Descending** order support
- **Pagination** with configurable page sizes
- **Metadata** including total count, page info, and navigation flags

### Smart Features
- **Autocomplete Suggestions** based on existing task content
- **Filter Statistics** to show available filter options
- **Search Performance Metrics** for monitoring
- **Result Caching** for improved performance
- **Cache Invalidation** on data changes

## API Endpoints

### Search Tasks

#### GET `/api/search/tasks`
Search and filter tasks with query parameters.

```http
GET /api/search/tasks?query=Python&priority=high&page=1&size=20
Authorization: Bearer jwt-token
```

**Query Parameters:**
- `query` (string, optional): Search text for titles and descriptions
- `completed` (boolean, optional): Filter by completion status
- `priority` (string, optional): Filter by priority (comma-separated for multiple)
- `due_date_from` (date, optional): Filter by due date from (YYYY-MM-DD)
- `due_date_to` (date, optional): Filter by due date to (YYYY-MM-DD)
- `created_from` (date, optional): Filter by creation date from
- `created_to` (date, optional): Filter by creation date to
- `sort_by` (enum, optional): Field to sort by (`created_at`, `title`, `priority`, `due_date`, `completed`)
- `sort_order` (enum, optional): Sort order (`asc`, `desc`)
- `page` (integer, optional): Page number (default: 1)
- `size` (integer, optional): Page size (default: 20, max: 100)

**Response:**
```json
{
  "tasks": [
    {
      "id": 1,
      "title": "Learn Python Programming",
      "description": "Study Python fundamentals",
      "completed": false,
      "priority": "high",
      "due_date": "2024-12-17T00:00:00",
      "user_id": 1,
      "created_at": "2024-12-10T10:00:00",
      "updated_at": "2024-12-10T10:00:00"
    }
  ],
  "total": 25,
  "page": 1,
  "size": 20,
  "total_pages": 2,
  "has_next": true,
  "has_prev": false,
  "search_time_ms": 15.5
}
```

#### POST `/api/search/tasks`
Search tasks using POST for complex queries.

```http
POST /api/search/tasks
Authorization: Bearer jwt-token
Content-Type: application/json

{
  "query": "Python API",
  "priority": "high,medium",
  "completed": false,
  "due_date_from": "2024-12-10",
  "due_date_to": "2024-12-31",
  "sort_by": "due_date",
  "sort_order": "asc",
  "page": 1,
  "size": 10
}
```

### Autocomplete Suggestions

#### GET `/api/search/suggestions`
Get search suggestions for autocomplete.

```http
GET /api/search/suggestions?q=Py&limit=10
Authorization: Bearer jwt-token
```

**Response:**
```json
{
  "suggestions": [
    "Python",
    "PyTest",
    "Python Programming"
  ],
  "query": "Py"
}
```

### Filter Statistics

#### GET `/api/search/filters/stats`
Get statistics for building filter UI components.

```http
GET /api/search/filters/stats
Authorization: Bearer jwt-token
```

**Response:**
```json
{
  "priorities": {
    "high": 5,
    "medium": 8,
    "low": 3
  },
  "completion": {
    "false": 12,
    "true": 4
  },
  "date_ranges": {
    "created_from": "2024-11-01T00:00:00",
    "created_to": "2024-12-10T15:30:00",
    "due_from": "2024-12-05T00:00:00",
    "due_to": "2024-12-31T00:00:00"
  },
  "total_tasks": 16
}
```

### Cache Management

#### DELETE `/api/search/cache`
Clear search cache for the current user.

```http
DELETE /api/search/cache
Authorization: Bearer jwt-token
```

### Advanced Features

#### GET `/api/search/advanced/fields`
Get searchable fields metadata for building advanced search forms.

#### GET `/api/search/export`
Export search results in various formats.

```http
GET /api/search/export?format=json&query=Python&priority=high
Authorization: Bearer jwt-token
```

## Search Query Syntax

### Basic Text Search
```
Python              # Find tasks containing "Python"
API development     # Find tasks containing both "API" and "development"
```

### Quoted Phrases
```
"REST API"          # Find exact phrase "REST API"
"machine learning"  # Find exact phrase "machine learning"
```

### Combined Search
```
Python "REST API" framework    # Find tasks with "Python", exact phrase "REST API", and "framework"
```

## Filtering Examples

### Single Filters
```http
# High priority tasks only
GET /api/search/tasks?priority=high

# Completed tasks only
GET /api/search/tasks?completed=true

# Tasks due this week
GET /api/search/tasks?due_date_from=2024-12-10&due_date_to=2024-12-17
```

### Combined Filters
```http
# High priority incomplete tasks about Python
GET /api/search/tasks?query=Python&priority=high&completed=false

# Multiple priorities
GET /api/search/tasks?priority=high,medium

# Date range with text search
GET /api/search/tasks?query=API&created_from=2024-12-01&created_to=2024-12-10
```

## Sorting Options

### Available Sort Fields
- `created_at` - Task creation date (default)
- `updated_at` - Last modification date
- `due_date` - Task due date
- `title` - Task title (alphabetical)
- `priority` - Task priority (high > medium > low)
- `completed` - Completion status

### Sort Examples
```http
# Latest tasks first
GET /api/search/tasks?sort_by=created_at&sort_order=desc

# Alphabetical by title
GET /api/search/tasks?sort_by=title&sort_order=asc

# Due date ascending (soonest first)
GET /api/search/tasks?sort_by=due_date&sort_order=asc
```

## Performance & Caching

### Caching Strategy
- **Search Results** cached for 5 minutes for non-text queries
- **Suggestions** cached for 1 hour
- **Filter Statistics** cached for 30 minutes
- **Automatic Invalidation** when tasks are modified

### Cache Keys
```
search:user_1_completed_false_priority_high_...    # Search results
suggestions:user_1_suggestions_py                  # Autocomplete suggestions
stats:user_1_filter_stats                         # Filter statistics
```

### Performance Optimization
- SQLite indexes on searchable fields
- Efficient pagination with LIMIT/OFFSET
- Result caching for repeated queries
- Query optimization for combined filters

## Usage Examples

### Frontend Integration

#### React Component Example
```javascript
// Search component
const [searchQuery, setSearchQuery] = useState('');
const [filters, setFilters] = useState({
  priority: '',
  completed: null,
  sortBy: 'created_at',
  sortOrder: 'desc'
});

const searchTasks = async () => {
  const params = new URLSearchParams({
    query: searchQuery,
    priority: filters.priority,
    completed: filters.completed,
    sort_by: filters.sortBy,
    sort_order: filters.sortOrder,
    page: 1,
    size: 20
  });
  
  const response = await fetch(`/api/search/tasks?${params}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  
  const results = await response.json();
  setTasks(results.tasks);
  setPagination({
    total: results.total,
    page: results.page,
    totalPages: results.total_pages,
    hasNext: results.has_next,
    hasPrev: results.has_prev
  });
};
```

#### Autocomplete Example
```javascript
const [suggestions, setSuggestions] = useState([]);

const getSuggestions = async (query) => {
  if (query.length < 2) return;
  
  const response = await fetch(`/api/search/suggestions?q=${query}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  
  const data = await response.json();
  setSuggestions(data.suggestions);
};

// Use debounced input for better performance
const debouncedGetSuggestions = debounce(getSuggestions, 300);
```

### curl Examples

#### Basic Search
```bash
# Search for Python tasks
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/search/tasks?query=Python"

# High priority incomplete tasks
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/search/tasks?priority=high&completed=false"
```

#### Complex Search with POST
```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Python API",
    "priority": "high,medium", 
    "completed": false,
    "sort_by": "due_date",
    "sort_order": "asc",
    "page": 1,
    "size": 10
  }' \
  "http://localhost:8000/api/search/tasks"
```

#### Get Suggestions
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/search/suggestions?q=Py&limit=5"
```

## Error Handling

### Common Error Responses

#### 400 Bad Request
```json
{
  "detail": "Invalid date format. Use YYYY-MM-DD"
}
```

#### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["query", "q"],
      "msg": "ensure this value has at least 2 characters",
      "type": "value_error.any_str.min_length"
    }
  ]
}
```

#### 500 Internal Server Error
```json
{
  "detail": "Search failed: Database connection error"
}
```

## Monitoring & Analytics

### Search Metrics
- **Search Time**: Included in response as `search_time_ms`
- **Cache Hit Rate**: Monitor cache effectiveness
- **Popular Queries**: Track frequently searched terms
- **Filter Usage**: Monitor which filters are used most

### Performance Monitoring
```python
# Example monitoring
search_time = response.json().get('search_time_ms', 0)
if search_time > 1000:  # 1 second threshold
    logger.warning(f"Slow search detected: {search_time}ms")
```

## Testing

### Run Search Tests
```bash
# Run all search tests
python -m pytest test_search.py -v

# Run search verification
python verify_search.py
```

### Test Coverage
- ✅ Basic text search
- ✅ Multi-keyword search
- ✅ Priority filtering
- ✅ Date range filtering
- ✅ Completion status filtering
- ✅ Combined filters
- ✅ Sorting functionality
- ✅ Pagination
- ✅ Autocomplete suggestions
- ✅ Filter statistics
- ✅ Cache invalidation
- ✅ Performance metrics
- ✅ Export functionality

## Best Practices

### Frontend Implementation
1. **Debounce** search input for better performance
2. **Show loading states** during search operations
3. **Cache suggestions** to reduce API calls
4. **Implement pagination** for large result sets
5. **Show search metrics** for user feedback

### Query Optimization
1. **Use specific filters** to reduce result sets
2. **Combine filters** rather than multiple requests
3. **Leverage caching** for repeated searches
4. **Use pagination** instead of loading all results

### User Experience
1. **Provide autocomplete** for better discoverability
2. **Show filter statistics** to guide user choices
3. **Preserve search state** in URL parameters
4. **Offer search suggestions** based on user's data

## Troubleshooting

### Common Issues

#### Slow Search Performance
```bash
# Check search time in response
# If > 1000ms, consider:
# 1. Adding database indexes
# 2. Reducing result set size
# 3. Optimizing query complexity
```

#### No Search Results
```bash
# Verify query syntax
# Check user permissions
# Ensure data exists
# Test with simpler queries
```

#### Cache Issues
```bash
# Clear search cache
curl -X DELETE -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/search/cache"
```

### Debug Mode
```python
# Enable search debugging
import logging
logging.getLogger('search').setLevel(logging.DEBUG)
```

## Future Enhancements

### Planned Features
- **Elasticsearch Integration** for advanced search
- **Search History** tracking
- **Saved Searches** functionality
- **Search Analytics** dashboard
- **Advanced Operators** (AND, OR, NOT)
- **Tag-based Search** when tags are implemented
- **Full-text Ranking** with relevance scoring

### Performance Improvements
- **Database Indexes** optimization
- **Query Result Pooling**
- **Background Search Indexing**
- **Search Result Preloading**

---

**Last Updated**: Task 6 Implementation
**Version**: 1.0.0
**Dependencies**: FastAPI, SQLAlchemy, Redis, Pydantic