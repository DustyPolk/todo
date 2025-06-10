import { useState } from 'react';
import type { Task } from '../types/task';
import { useUpdateTask, useDeleteTask } from '../hooks/useTasks';
import { Button } from './ui/button';
import { Checkbox } from './ui/checkbox';
import { Card, CardContent } from './ui/card';
import { Trash2, Edit, Calendar, AlertCircle } from 'lucide-react';

interface TaskItemProps {
  task: Task;
  onEdit: (task: Task) => void;
}

const priorityColors = {
  low: 'text-green-600',
  medium: 'text-yellow-600',
  high: 'text-red-600',
};


export function TaskItem({ task, onEdit }: TaskItemProps) {
  const [isUpdating, setIsUpdating] = useState(false);
  const updateTask = useUpdateTask();
  const deleteTask = useDeleteTask();

  const handleToggleComplete = async () => {
    setIsUpdating(true);
    try {
      await updateTask.mutateAsync({
        id: task.id,
        task: { completed: !task.completed }
      });
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDelete = async () => {
    if (window.confirm('Are you sure you want to delete this task?')) {
      await deleteTask.mutateAsync(task.id);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  return (
    <Card className={`transition-opacity ${task.completed ? 'opacity-75' : ''}`}>
      <CardContent className="p-4">
        <div className="flex items-start space-x-3">
          <Checkbox
            checked={task.completed}
            onCheckedChange={handleToggleComplete}
            disabled={isUpdating}
            className="mt-1"
          />
          
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between">
              <h3 className={`font-medium ${task.completed ? 'line-through text-muted-foreground' : ''}`}>
                {task.title}
              </h3>
              
              <div className="flex items-center space-x-2">
                {task.priority !== 'medium' && (
                  <AlertCircle className={`h-4 w-4 ${priorityColors[task.priority]}`} />
                )}
                
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onEdit(task)}
                  className="h-8 w-8 p-0"
                >
                  <Edit className="h-4 w-4" />
                </Button>
                
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleDelete}
                  className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                  disabled={deleteTask.isPending}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
            
            {task.description && (
              <p className={`text-sm mt-1 ${task.completed ? 'line-through text-muted-foreground' : 'text-muted-foreground'}`}>
                {task.description}
              </p>
            )}
            
            <div className="flex items-center justify-between mt-2">
              <div className="flex items-center space-x-4 text-xs text-muted-foreground">
                <span className={`capitalize ${priorityColors[task.priority]}`}>
                  {task.priority} priority
                </span>
                
                {task.due_date && (
                  <div className="flex items-center space-x-1">
                    <Calendar className="h-3 w-3" />
                    <span>{formatDate(task.due_date)}</span>
                  </div>
                )}
              </div>
              
              <span className="text-xs text-muted-foreground">
                Created {formatDate(task.created_at)}
              </span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}