import type { Task, TaskCreate, TaskUpdate } from '../types/task';

// Use relative URL since we're proxying through Vite dev server
const API_BASE_URL = '/api';

class ApiService {
  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
  }

  async getTasks(params?: {
    completed?: boolean;
    priority?: string;
    skip?: number;
    limit?: number;
  }): Promise<Task[]> {
    const searchParams = new URLSearchParams();
    
    if (params?.completed !== undefined) {
      searchParams.append('completed', params.completed.toString());
    }
    if (params?.priority) {
      searchParams.append('priority', params.priority);
    }
    if (params?.skip !== undefined) {
      searchParams.append('skip', params.skip.toString());
    }
    if (params?.limit !== undefined) {
      searchParams.append('limit', params.limit.toString());
    }

    const endpoint = `/tasks${searchParams.toString() ? `?${searchParams.toString()}` : ''}`;
    return this.request<Task[]>(endpoint);
  }

  async getTask(id: number): Promise<Task> {
    return this.request<Task>(`/tasks/${id}`);
  }

  async createTask(task: TaskCreate): Promise<Task> {
    return this.request<Task>('/tasks', {
      method: 'POST',
      body: JSON.stringify(task),
    });
  }

  async updateTask(id: number, task: TaskUpdate): Promise<Task> {
    return this.request<Task>(`/tasks/${id}`, {
      method: 'PUT',
      body: JSON.stringify(task),
    });
  }

  async deleteTask(id: number): Promise<void> {
    await this.request<void>(`/tasks/${id}`, {
      method: 'DELETE',
    });
  }

  async getStats(): Promise<{
    total_tasks: number;
    completed_tasks: number;
    active_tasks: number;
  }> {
    return this.request<{
      total_tasks: number;
      completed_tasks: number;
      active_tasks: number;
    }>('/stats');
  }
}

export const apiService = new ApiService();