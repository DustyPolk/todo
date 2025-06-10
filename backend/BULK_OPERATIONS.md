# Bulk Operations and Task Management Documentation

## Overview

The Todo API provides comprehensive bulk operations and advanced task management capabilities designed to handle multiple tasks efficiently. The system supports atomic transactions, progress tracking, undo/redo functionality, drag-and-drop reordering, and task templates for common workflows.

## Features

### Core Bulk Operations
- **Bulk Task Creation** - Create multiple tasks in a single operation
- **Bulk Updates** - Update multiple tasks simultaneously
- **Bulk Deletion** - Delete multiple tasks with undo support
- **Bulk Status Changes** - Mark multiple tasks as complete/incomplete
- **Bulk Priority Changes** - Change priority for multiple tasks
- **Task Duplication** - Create copies of existing tasks

### Advanced Task Management
- **Drag-and-Drop Reordering** - Reorder tasks with optimistic updates
- **Task Templates** - Create reusable task sets for common workflows
- **Undo/Redo System** - Reverse bulk operations with full state restoration
- **Progress Tracking** - Real-time progress monitoring for long operations
- **Keyboard Shortcuts** - Full keyboard navigation and bulk actions

### Performance & Reliability
- **Atomic Transactions** - All operations succeed or fail together
- **Background Processing** - Long operations run asynchronously
- **Conflict Resolution** - Handle concurrent modifications gracefully
- **Cache Integration** - Automatic cache invalidation on changes
- **Error Recovery** - Detailed error reporting and recovery options

## API Endpoints

### Bulk Task Creation

#### POST `/api/bulk/create`
Create multiple tasks in bulk with atomic transaction support.

```http
POST /api/bulk/create
Authorization: Bearer jwt-token
Content-Type: application/json

{
  "tasks": [
    {
      "title": "Setup Development Environment",
      "description": "Install required tools and dependencies",
      "priority": "high",
      "due_date": "2024-12-20T00:00:00"
    },
    {
      "title": "Write Unit Tests",
      "description": "Add test coverage for new features",
      "priority": "medium"
    },
    {
      "title": "Update Documentation", 
      "description": "Document new API endpoints",
      "priority": "low"
    }
  ]
}
```

**Response:**
```json
{
  "operation_id": "bulk_op_123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "message": "Successfully created 3 tasks",
  "total_items": 3,
  "processed_items": 3,
  "failed_items": 0,
  "progress_percentage": 100.0,
  "created_tasks": [
    {
      "id": 101,
      "title": "Setup Development Environment",
      "description": "Install required tools and dependencies",
      "completed": false,
      "priority": "high",
      "due_date": "2024-12-20T00:00:00",
      "user_id": 1,
      "created_at": "2024-12-10T15:30:00",
      "updated_at": "2024-12-10T15:30:00"
    }
  ]
}
```

### Bulk Task Updates

#### PUT `/api/bulk/update`
Update multiple tasks with flexible field modifications.

```http
PUT /api/bulk/update
Authorization: Bearer jwt-token
Content-Type: application/json

{
  "task_ids": [101, 102, 103],
  "update_data": {
    "priority": "high",
    "completed": false,
    "due_date": "2024-12-25T00:00:00"
  }
}
```

#### PUT `/api/bulk/status`
Change completion status for multiple tasks.

```http
PUT /api/bulk/status
Authorization: Bearer jwt-token
Content-Type: application/json

{
  "task_ids": [101, 102, 103],
  "completed": true
}
```

#### PUT `/api/bulk/priority`
Change priority for multiple tasks.

```http
PUT /api/bulk/priority
Authorization: Bearer jwt-token
Content-Type: application/json

{
  "task_ids": [101, 102, 103],
  "priority": "high"
}
```

### Bulk Task Deletion

#### DELETE `/api/bulk/delete`
Delete multiple tasks with undo support.

```http
DELETE /api/bulk/delete
Authorization: Bearer jwt-token
Content-Type: application/json

{
  "task_ids": [101, 102, 103]
}
```

**Response:**
```json
{
  "operation_id": "bulk_op_456e7890-e89b-12d3-a456-426614174001",
  "status": "completed",
  "message": "Successfully deleted 3 tasks",
  "total_items": 3,
  "processed_items": 3,
  "failed_items": 0,
  "progress_percentage": 100.0
}
```

### Task Reordering

#### PUT `/api/bulk/reorder`
Reorder tasks for drag-and-drop functionality.

```http
PUT /api/bulk/reorder
Authorization: Bearer jwt-token
Content-Type: application/json

{
  "task_positions": [
    {"id": 101, "position": 0},
    {"id": 102, "position": 1},
    {"id": 103, "position": 2}
  ]
}
```

### Task Duplication

#### POST `/api/bulk/duplicate`
Create copies of existing tasks.

```http
POST /api/bulk/duplicate
Authorization: Bearer jwt-token
Content-Type: application/json

{
  "task_ids": [101, 102],
  "suffix": " (Copy)"
}
```

**Response:**
```json
{
  "operation_id": "bulk_op_789e0123-e89b-12d3-a456-426614174002",
  "status": "completed",
  "message": "Successfully duplicated 2 tasks",
  "total_items": 2,
  "processed_items": 2,
  "failed_items": 0,
  "progress_percentage": 100.0,
  "duplicated_tasks": [
    {
      "id": 104,
      "title": "Setup Development Environment (Copy)",
      "description": "Install required tools and dependencies",
      "completed": false,
      "priority": "high",
      "user_id": 1,
      "created_at": "2024-12-10T15:45:00",
      "updated_at": "2024-12-10T15:45:00"
    }
  ]
}
```

### Operation Status Tracking

#### GET `/api/bulk/status/{operation_id}`
Get the status of a bulk operation.

```http
GET /api/bulk/status/bulk_op_123e4567-e89b-12d3-a456-426614174000
Authorization: Bearer jwt-token
```

**Response:**
```json
{
  "operation_id": "bulk_op_123e4567-e89b-12d3-a456-426614174000",
  "operation_type": "create",
  "status": "completed",
  "total_items": 10,
  "processed_items": 10,
  "failed_items": 0,
  "progress_percentage": 100.0,
  "created_at": "2024-12-10T15:30:00",
  "started_at": "2024-12-10T15:30:01",
  "completed_at": "2024-12-10T15:30:05",
  "error_message": null,
  "is_completed": true
}
```

### Undo/Redo System

#### POST `/api/bulk/undo`
Undo a bulk operation.

```http
POST /api/bulk/undo
Authorization: Bearer jwt-token
Content-Type: application/json

{
  "operation_id": "bulk_op_123e4567-e89b-12d3-a456-426614174000"
}
```

If no operation_id is provided, undoes the most recent operation.

#### GET `/api/bulk/undo/history`
Get undo history for the current user.

```http
GET /api/bulk/undo/history
Authorization: Bearer jwt-token
```

**Response:**
```json
{
  "undo_history": [
    {
      "id": "bulk_op_123e4567-e89b-12d3-a456-426614174000",
      "operation_type": "delete",
      "total_items": 5,
      "created_at": "2024-12-10T15:30:00",
      "can_undo": true
    },
    {
      "id": "bulk_op_456e7890-e89b-12d3-a456-426614174001",
      "operation_type": "update",
      "total_items": 3,
      "created_at": "2024-12-10T15:25:00",
      "can_undo": true
    }
  ]
}
```

## Task Templates

### Create Template

#### POST `/api/bulk/templates`
Create a reusable task template.

```http
POST /api/bulk/templates
Authorization: Bearer jwt-token
Content-Type: application/json

{
  "name": "Project Setup",
  "description": "Standard project initialization tasks",
  "category": "development",
  "is_public": false,
  "tasks": [
    {
      "title": "Initialize Git Repository",
      "description": "Set up version control",
      "priority": "high"
    },
    {
      "title": "Setup Development Environment",
      "description": "Install dependencies and tools",
      "priority": "medium"
    },
    {
      "title": "Create Project Documentation",
      "description": "Write README and setup docs",
      "priority": "low"
    }
  ]
}
```

### Get Templates

#### GET `/api/bulk/templates`
Get available task templates.

```http
GET /api/bulk/templates?category=development&include_public=true
Authorization: Bearer jwt-token
```

**Response:**
```json
{
  "templates": [
    {
      "id": "template_123e4567-e89b-12d3-a456-426614174000",
      "name": "Project Setup",
      "description": "Standard project initialization tasks",
      "category": "development",
      "task_count": 3,
      "is_public": false,
      "created_at": "2024-12-10T10:00:00"
    }
  ]
}
```

### Apply Template

#### POST `/api/bulk/templates/apply`
Apply a template to create tasks.

```http
POST /api/bulk/templates/apply
Authorization: Bearer jwt-token
Content-Type: application/json

{
  "template_id": "template_123e4567-e89b-12d3-a456-426614174000",
  "customizations": {
    "priority": "high",
    "due_date": "2024-12-20T00:00:00"
  }
}
```

## Keyboard Shortcuts

### Get Shortcuts Information

#### GET `/api/bulk/shortcuts`
Get available keyboard shortcuts and their mappings.

```http
GET /api/bulk/shortcuts
Authorization: Bearer jwt-token
```

**Response:**
```json
{
  "shortcuts": {
    "Ctrl+A / Cmd+A": "Select all tasks",
    "Delete": "Delete selected tasks",
    "Ctrl+D / Cmd+D": "Duplicate selected tasks",
    "Ctrl+Z / Cmd+Z": "Undo last operation",
    "Ctrl+Shift+Z / Cmd+Shift+Z": "Redo operation",
    "Space": "Toggle completion status",
    "1": "Set priority to high",
    "2": "Set priority to medium",
    "3": "Set priority to low",
    "Enter": "Edit selected task",
    "Escape": "Clear selection"
  },
  "bulk_operations": {
    "select_all": "/api/search/tasks",
    "bulk_delete": "/api/bulk/delete",
    "bulk_duplicate": "/api/bulk/duplicate",
    "bulk_status": "/api/bulk/status",
    "bulk_priority": "/api/bulk/priority",
    "undo": "/api/bulk/undo"
  }
}
```

## Frontend Integration

### React Component Examples

#### Bulk Operations Context
```javascript
// BulkOperationsContext.js
import React, { createContext, useContext, useState } from 'react';

const BulkOperationsContext = createContext();

export const useBulkOperations = () => {
  const context = useContext(BulkOperationsContext);
  if (!context) {
    throw new Error('useBulkOperations must be used within BulkOperationsProvider');
  }
  return context;
};

export const BulkOperationsProvider = ({ children }) => {
  const [selectedTasks, setSelectedTasks] = useState(new Set());
  const [operationInProgress, setOperationInProgress] = useState(false);
  const [lastOperation, setLastOperation] = useState(null);

  const selectTask = (taskId) => {
    setSelectedTasks(prev => new Set([...prev, taskId]));
  };

  const deselectTask = (taskId) => {
    setSelectedTasks(prev => {
      const newSet = new Set(prev);
      newSet.delete(taskId);
      return newSet;
    });
  };

  const selectAllTasks = (taskIds) => {
    setSelectedTasks(new Set(taskIds));
  };

  const clearSelection = () => {
    setSelectedTasks(new Set());
  };

  const bulkDelete = async () => {
    if (selectedTasks.size === 0) return;

    setOperationInProgress(true);
    try {
      const response = await fetch('/api/bulk/delete', {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          task_ids: Array.from(selectedTasks)
        })
      });

      const result = await response.json();
      setLastOperation(result);
      clearSelection();
      
      // Refresh task list
      await refreshTasks();
    } catch (error) {
      console.error('Bulk delete failed:', error);
    } finally {
      setOperationInProgress(false);
    }
  };

  const bulkStatusChange = async (completed) => {
    if (selectedTasks.size === 0) return;

    setOperationInProgress(true);
    try {
      const response = await fetch('/api/bulk/status', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          task_ids: Array.from(selectedTasks),
          completed
        })
      });

      const result = await response.json();
      setLastOperation(result);
      clearSelection();
      
      await refreshTasks();
    } catch (error) {
      console.error('Bulk status change failed:', error);
    } finally {
      setOperationInProgress(false);
    }
  };

  const undo = async () => {
    try {
      const response = await fetch('/api/bulk/undo', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        await refreshTasks();
        setLastOperation(null);
      }
    } catch (error) {
      console.error('Undo failed:', error);
    }
  };

  return (
    <BulkOperationsContext.Provider value={{
      selectedTasks,
      operationInProgress,
      lastOperation,
      selectTask,
      deselectTask,
      selectAllTasks,
      clearSelection,
      bulkDelete,
      bulkStatusChange,
      undo
    }}>
      {children}
    </BulkOperationsContext.Provider>
  );
};
```

#### Keyboard Shortcuts Hook
```javascript
// useKeyboardShortcuts.js
import { useEffect } from 'react';
import { useBulkOperations } from './BulkOperationsContext';

export const useKeyboardShortcuts = (tasks, isEnabled = true) => {
  const {
    selectedTasks,
    selectAllTasks,
    clearSelection,
    bulkDelete,
    bulkStatusChange,
    undo
  } = useBulkOperations();

  useEffect(() => {
    if (!isEnabled) return;

    const handleKeyDown = (event) => {
      // Ignore if user is typing in an input
      if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
        return;
      }

      const { key, ctrlKey, metaKey, shiftKey } = event;
      const isModifierPressed = ctrlKey || metaKey;

      switch (key) {
        case 'a':
        case 'A':
          if (isModifierPressed) {
            event.preventDefault();
            selectAllTasks(tasks.map(task => task.id));
          }
          break;

        case 'Delete':
        case 'Backspace':
          if (selectedTasks.size > 0) {
            event.preventDefault();
            bulkDelete();
          }
          break;

        case 'd':
        case 'D':
          if (isModifierPressed && selectedTasks.size > 0) {
            event.preventDefault();
            // Trigger bulk duplicate
            duplicateSelectedTasks();
          }
          break;

        case 'z':
        case 'Z':
          if (isModifierPressed && !shiftKey) {
            event.preventDefault();
            undo();
          }
          break;

        case ' ':
          if (selectedTasks.size > 0) {
            event.preventDefault();
            // Toggle completion status
            bulkStatusChange(!isAnySelectedCompleted());
          }
          break;

        case '1':
          if (selectedTasks.size > 0) {
            event.preventDefault();
            bulkPriorityChange('high');
          }
          break;

        case '2':
          if (selectedTasks.size > 0) {
            event.preventDefault();
            bulkPriorityChange('medium');
          }
          break;

        case '3':
          if (selectedTasks.size > 0) {
            event.preventDefault();
            bulkPriorityChange('low');
          }
          break;

        case 'Escape':
          clearSelection();
          break;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isEnabled, selectedTasks, tasks]);
};
```

#### Drag and Drop Component
```javascript
// DragDropTaskList.js
import React from 'react';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';

export const DragDropTaskList = ({ tasks, onReorder }) => {
  const handleDragEnd = async (result) => {
    if (!result.destination) return;

    const sourceIndex = result.source.index;
    const destinationIndex = result.destination.index;

    if (sourceIndex === destinationIndex) return;

    // Optimistic update
    const newTasks = Array.from(tasks);
    const [reorderedTask] = newTasks.splice(sourceIndex, 1);
    newTasks.splice(destinationIndex, 0, reorderedTask);

    // Update UI immediately
    onReorder(newTasks);

    // Send reorder request to API
    try {
      const taskPositions = newTasks.map((task, index) => ({
        id: task.id,
        position: index
      }));

      const response = await fetch('/api/bulk/reorder', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ task_positions: taskPositions })
      });

      if (!response.ok) {
        // Revert on failure
        onReorder(tasks);
        console.error('Reorder failed');
      }
    } catch (error) {
      // Revert on error
      onReorder(tasks);
      console.error('Reorder error:', error);
    }
  };

  return (
    <DragDropContext onDragEnd={handleDragEnd}>
      <Droppable droppableId="task-list">
        {(provided) => (
          <div
            {...provided.droppableProps}
            ref={provided.innerRef}
            className="task-list"
          >
            {tasks.map((task, index) => (
              <Draggable
                key={task.id}
                draggableId={task.id.toString()}
                index={index}
              >
                {(provided, snapshot) => (
                  <div
                    ref={provided.innerRef}
                    {...provided.draggableProps}
                    {...provided.dragHandleProps}
                    className={`task-item ${snapshot.isDragging ? 'dragging' : ''}`}
                  >
                    <TaskItem task={task} />
                  </div>
                )}
              </Draggable>
            ))}
            {provided.placeholder}
          </div>
        )}
      </Droppable>
    </DragDropContext>
  );
};
```

### Progress Tracking
```javascript
// ProgressTracker.js
import React, { useState, useEffect } from 'react';

export const ProgressTracker = ({ operationId, onComplete }) => {
  const [progress, setProgress] = useState(null);
  const [polling, setPolling] = useState(true);

  useEffect(() => {
    if (!operationId || !polling) return;

    const pollProgress = async () => {
      try {
        const response = await fetch(`/api/bulk/status/${operationId}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
          const data = await response.json();
          setProgress(data);

          if (data.is_completed) {
            setPolling(false);
            onComplete?.(data);
          }
        }
      } catch (error) {
        console.error('Progress polling failed:', error);
        setPolling(false);
      }
    };

    const interval = setInterval(pollProgress, 1000); // Poll every second
    pollProgress(); // Initial call

    return () => clearInterval(interval);
  }, [operationId, polling]);

  if (!progress) return null;

  return (
    <div className="progress-tracker">
      <div className="progress-header">
        <h4>{progress.operation_type} Operation</h4>
        <span className="status">{progress.status}</span>
      </div>
      
      <div className="progress-bar">
        <div 
          className="progress-fill"
          style={{ width: `${progress.progress_percentage}%` }}
        />
      </div>
      
      <div className="progress-details">
        <span>{progress.processed_items} / {progress.total_items} items</span>
        <span>{progress.progress_percentage.toFixed(1)}%</span>
      </div>
      
      {progress.error_message && (
        <div className="error-message">
          Error: {progress.error_message}
        </div>
      )}
    </div>
  );
};
```

## Performance Considerations

### Optimization Strategies

1. **Batch Size Limits**
   - Maximum 100 tasks for creation/duplication
   - Maximum 1000 tasks for updates/deletion
   - Chunked processing for large operations

2. **Database Optimization**
   - Uses transactions for atomicity
   - Bulk insert/update operations
   - Proper indexing on frequently queried fields

3. **Caching Strategy**
   - Automatic cache invalidation on bulk changes
   - Operation status caching
   - Template caching for reuse

4. **Error Handling**
   - Graceful degradation on partial failures
   - Detailed error reporting per item
   - Transaction rollback on critical errors

### Monitoring & Metrics

```javascript
// Example metrics tracking
const trackBulkOperation = async (operationType, itemCount, duration) => {
  await fetch('/api/metrics/bulk-operation', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      operation_type: operationType,
      item_count: itemCount,
      duration_ms: duration,
      timestamp: new Date().toISOString()
    })
  });
};
```

## Testing

### Run Bulk Operations Tests
```bash
# Run all bulk operations tests
python -m pytest test_bulk_operations.py -v

# Run bulk operations verification
python verify_bulk_operations.py
```

### Test Coverage
- ✅ Bulk task creation with validation
- ✅ Bulk updates (status, priority, fields)
- ✅ Bulk deletion with undo support
- ✅ Task reordering for drag-and-drop
- ✅ Task duplication with suffix
- ✅ Operation status tracking
- ✅ Progress monitoring
- ✅ Undo/redo functionality
- ✅ Task templates (create, apply, list)
- ✅ Keyboard shortcuts support
- ✅ Input validation and limits
- ✅ Error handling and recovery
- ✅ Cache invalidation
- ✅ Transaction atomicity

## Best Practices

### Frontend Implementation
1. **Use optimistic updates** for better UX during reordering
2. **Implement progress indicators** for long-running operations
3. **Provide keyboard shortcuts** for power users
4. **Show undo notifications** with action buttons
5. **Batch UI updates** to avoid performance issues

### Backend Optimization
1. **Use database transactions** for atomicity
2. **Implement proper pagination** for large result sets
3. **Cache frequently used templates**
4. **Monitor operation performance**
5. **Set reasonable batch size limits**

### User Experience
1. **Provide clear feedback** on operation status
2. **Support both mouse and keyboard** interactions
3. **Implement drag-and-drop** for intuitive reordering
4. **Show progress for long operations**
5. **Enable quick undo** for reversible actions

## Troubleshooting

### Common Issues

#### Operation Timeout
```bash
# Check operation status
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/bulk/status/operation_id"

# Monitor progress for long operations
# Operations timeout after 10 minutes by default
```

#### Partial Failures
```javascript
// Handle partial failures gracefully
const handleBulkResult = (result) => {
  if (result.failed_items > 0) {
    showWarning(`${result.failed_items} items failed to process`);
  }
  
  if (result.processed_items > 0) {
    showSuccess(`${result.processed_items} items processed successfully`);
  }
};
```

#### Cache Inconsistency
```bash
# Clear all caches if data seems stale
curl -X DELETE -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/cache/clear"

curl -X DELETE -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/search/cache"
```

### Debug Mode
```python
# Enable bulk operations debugging
import logging
logging.getLogger('bulk_operations').setLevel(logging.DEBUG)
```

## Future Enhancements

### Planned Features
- **Bulk Import/Export** from CSV, JSON files
- **Advanced Templates** with conditional logic
- **Scheduled Bulk Operations** for automation
- **Bulk Tag Management** when tags are implemented
- **Operation Queueing** for resource management
- **Conflict Resolution UI** for concurrent edits

### Performance Improvements
- **Background Job Processing** for very large operations
- **Database Connection Pooling** optimization
- **Redis-based Operation Queuing**
- **Batch Progress Streaming** via WebSockets

---

**Last Updated**: Task 7 Implementation
**Version**: 1.0.0
**Dependencies**: FastAPI, SQLAlchemy, Redis, Pydantic, UUID