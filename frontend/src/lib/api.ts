export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

const jsonHeaders = {
  'Content-Type': 'application/json',
};

const getErrorMessage = async (response: Response): Promise<string> => {
  try {
    const data = await response.json();
    if (typeof data?.detail === 'string') return data.detail;
    if (typeof data?.message === 'string') return data.message;
  } catch {
    // Ignore JSON parse errors and fall back to status text.
  }
  return response.statusText || `Request failed with status ${response.status}`;
};

const requestJson = async <T>(url: string, init?: RequestInit): Promise<T> => {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new ApiError(0, 'Network error');
  }

  if (!response.ok) {
    throw new ApiError(response.status, await getErrorMessage(response));
  }

  return (await response.json()) as T;
};

type ChatRequest = {
  message: string;
  video_path?: string;
  image_base64?: string;
  thread_id?: string;
};

type ChatResponse = {
  message: string;
  clip_path?: string | null;
  thread_id?: string;
};

type UploadResponse = {
  message: string;
  video_path?: string | null;
  task_id?: string | null;
};

type ProcessVideoResponse = {
  message: string;
  task_id: string;
};

type TaskStatusResponse = {
  task_id: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
};

type ResetMemoryResponse = {
  message: string;
};

export const sendChatMessage = (payload: ChatRequest) =>
  requestJson<ChatResponse>('/chat', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });

export const processVideo = (videoPath: string) =>
  requestJson<ProcessVideoResponse>('/process-video', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ video_path: videoPath }),
  });

export const getTaskStatus = (taskId: string) =>
  requestJson<TaskStatusResponse>(`/task-status/${encodeURIComponent(taskId)}`);

export const resetMemory = (threadId: string) =>
  requestJson<ResetMemoryResponse>('/reset-memory', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ thread_id: threadId }),
  });

export const uploadVideo = (file: File, onProgress?: (progressPercent: number) => void) =>
  new Promise<UploadResponse>((resolve, reject) => {
    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/upload-video');

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress((event.loaded / event.total) * 100);
      }
    };

    xhr.onerror = () => reject(new ApiError(0, 'Network error'));

    xhr.onload = () => {
      const status = xhr.status;
      let data: unknown = {};

      try {
        data = xhr.responseText ? JSON.parse(xhr.responseText) : {};
      } catch {
        // Ignore parse errors and use fallback message.
      }

      if (status < 200 || status >= 300) {
        const errorData =
          data && typeof data === 'object' ? (data as { detail?: string; message?: string }) : {};
        const message =
          typeof errorData.detail === 'string'
            ? errorData.detail
            : typeof errorData.message === 'string'
              ? errorData.message
              : `Request failed with status ${status}`;
        reject(new ApiError(status, message));
        return;
      }

      resolve(data as UploadResponse);
    };

    xhr.send(formData);
  });

export const deleteVideo = (videoPath: string) => {
  const videoName = videoPath.split('/').pop() ?? videoPath;
  return requestJson<{ index_removed: boolean; file_removed: boolean }>(
    `/videos/${encodeURIComponent(videoName)}`,
    { method: 'DELETE' },
  );
};

export const getMediaUrl = (filePath: string) => {
  const fileName = filePath.split('/').pop() ?? filePath;
  return `/media/${encodeURIComponent(fileName)}`;
};
