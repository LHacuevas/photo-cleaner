import { useState, useEffect } from 'react';
import { photosAPI } from '../services/api';

/**
 * Custom hook that polls the status of a background task
 * 
 * Usage:
 *   const { taskId, status, progress, isRunning, error } = useBackgroundTask();
 *   
 *   // Start a task
 *   const startTask = async () => {
 *     const response = await photosAPI.generateThumbsAsync(folderId);
 *     setTaskId(response.data.task_id);
 *   }
 */
function useBackgroundTask(taskId = null, pollInterval = 1000) {
  const [currentTaskId, setCurrentTaskId] = useState(taskId);
  const [status, setStatus] = useState(null);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (!currentTaskId) {
      setStatus(null);
      setProgress(0);
      return;
    }

    let mounted = true;
    let interval;

    const checkStatus = async () => {
      try {
        const response = await photosAPI.getTaskStatus(currentTaskId);
        
        if (!mounted) return;

        const taskData = response.data;
        setStatus(taskData.status);
        setProgress(taskData.progress || 0);
        setError(taskData.error || null);
        
        if (taskData.result) {
          setResult(taskData.result);
        }

        // Stop polling if task is complete
        if (['completed', 'failed', 'cancelled'].includes(taskData.status)) {
          if (interval) clearInterval(interval);
        }
      } catch (err) {
        // e.g. 404 after a backend restart (tasks live in memory): stop polling
        if (interval) clearInterval(interval);
        if (mounted) {
          setError(err.response?.status === 404 ? 'Task not found (backend restarted?)' : err.message);
          console.error('Error checking task status:', err);
        }
      }
    };

    // Check immediately
    checkStatus();

    // Then poll periodically
    interval = setInterval(checkStatus, pollInterval);

    return () => {
      mounted = false;
      if (interval) clearInterval(interval);
    };
  }, [currentTaskId, pollInterval]);

  const isRunning = status === 'running' || status === 'pending';

  return {
    taskId: currentTaskId,
    setTaskId: setCurrentTaskId,
    status,
    progress,
    isRunning,
    error,
    result
  };
}

export default useBackgroundTask;
