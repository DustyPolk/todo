import { useState } from 'react';
import type { Task } from '../types/task';
import { useTasks } from '../hooks/useTasks';
import { TaskItem } from './TaskItem';
import { TaskForm } from './TaskForm';
import { Button } from './ui/button';
import { Card, CardContent } from './ui/card';
import { ThemeToggle } from './ui/theme-toggle';
import { Plus, Filter, Loader2 } from 'lucide-react';

export function TaskList() {
  const [showForm, setShowForm] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [filter, setFilter] = useState<'all' | 'active' | 'completed'>('all');
  const [priorityFilter, setPriorityFilter] = useState<'all' | 'low' | 'medium' | 'high'>('all');

  const tasksQuery = useTasks({
    completed: filter === 'all' ? undefined : filter === 'completed',
    priority: priorityFilter === 'all' ? undefined : priorityFilter,
  });


  const handleEdit = (task: Task) => {
    setEditingTask(task);
    setShowForm(true);
  };

  const handleCloseForm = () => {
    setShowForm(false);
    setEditingTask(null);
  };

  if (tasksQuery.isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-8 w-8 animate-spin" />
        <span className="ml-2">Loading tasks...</span>
      </div>
    );
  }

  if (tasksQuery.error) {
    return (
      <Card className="p-8">
        <CardContent>
          <div className="text-center text-red-600">
            <p>Failed to load tasks. Please try again.</p>
            <Button
              onClick={() => tasksQuery.refetch()}
              variant="outline"
              className="mt-4"
            >
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const tasks = tasksQuery.data || [];

  return (
    <div className="space-y-6">
      {showForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <TaskForm task={editingTask || undefined} onClose={handleCloseForm} />
        </div>
      )}

      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h1 className="text-3xl font-bold">My Tasks</h1>
        <div className="flex items-center space-x-2">
          <ThemeToggle />
          <Button onClick={() => setShowForm(true)} className="flex items-center space-x-2">
            <Plus className="h-4 w-4" />
            <span>Add Task</span>
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex items-center space-x-2">
              <Filter className="h-4 w-4" />
              <span className="text-sm font-medium">Status:</span>
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value as 'all' | 'active' | 'completed')}
                className="text-sm border border-input bg-background text-foreground rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-ring [&>option]:bg-background [&>option]:text-foreground"
              >
                <option value="all">All</option>
                <option value="active">Active</option>
                <option value="completed">Completed</option>
              </select>
            </div>

            <div className="flex items-center space-x-2">
              <span className="text-sm font-medium">Priority:</span>
              <select
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value as 'all' | 'low' | 'medium' | 'high')}
                className="text-sm border border-input bg-background text-foreground rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-ring [&>option]:bg-background [&>option]:text-foreground"
              >
                <option value="all">All</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {tasks.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <p className="text-muted-foreground mb-4">
              {filter === 'all' ? 'No tasks yet.' : `No ${filter} tasks found.`}
            </p>
            <Button onClick={() => setShowForm(true)} variant="outline">
              <Plus className="h-4 w-4 mr-2" />
              Create your first task
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {tasks.map((task) => (
            <TaskItem key={task.id} task={task} onEdit={handleEdit} />
          ))}
        </div>
      )}
    </div>
  );
}