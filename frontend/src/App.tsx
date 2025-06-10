import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TaskList } from './components/TaskList';
import { ThemeProvider } from './components/hooks/use-theme';
import './App.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 10 * 60 * 1000, // 10 minutes
      retry: 1, // Only retry once to fail faster for debugging
    },
  },
});

function App() {
  return (
    <ThemeProvider defaultTheme="system" storageKey="todo-ui-theme">
      <QueryClientProvider client={queryClient}>
        <div className="min-h-screen bg-background transition-colors">
          <div className="container mx-auto py-8 px-4 max-w-4xl">
            <TaskList />
          </div>
        </div>
      </QueryClientProvider>
    </ThemeProvider>
  );
}

export default App;