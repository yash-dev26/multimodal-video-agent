import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import BackgroundAnimation from '@/components/BackgroundAnimation';
import ChatHeader from '@/components/ChatHeader';
import ChatInput from '@/components/ChatInput';
import Message from '@/components/Message';
import TypingIndicator from '@/components/TypingIndicator';
import VideoSidebar from '@/components/VideoSidebar';
import {
  ApiError,
  getTaskStatus,
  getMediaUrl,
  processVideo,
  resetMemory,
  sendChatMessage,
  uploadVideo,
} from '@/lib/api';

// ─── Types ────────────────────────────────────────────────────────────────────

interface MessageType {
  id: string;
  content: string;
  isUser: boolean;
  timestamp: Date;
  fileUrl?: string;
  fileType?: 'image' | 'video';
  clipPath?: string;
}

interface AttachedFile {
  url: string;
  type: 'image' | 'video';
  file: File;
}

interface UploadedVideo {
  id: string;
  url: string;
  file: File;
  timestamp: Date;
  videoPath?: string;
  taskId?: string;
  processingStatus?: 'pending' | 'in_progress' | 'completed' | 'failed';
}

// ─── Local storage keys ───────────────────────────────────────────────────────
const THREAD_ID_KEY = 'rocky_thread_id';

// ─── Offline fallback persona ─────────────────────────────────────────────────
const getOfflineRockyResponse = (
  userMsg: string,
  hasImage: boolean,
  hasVideo: boolean,
): string => {
  const text = userMsg.toLowerCase();
  if (hasImage) return 'I see the image, Grace! Very interesting. Amaze!';
  if (hasVideo) return 'Video loaded, Grace! What question do you have?';
  if (text.includes('sleep') || text.includes('rest')) return 'You sleep, Grace. I watch! Good, good, good.';
  if (text.includes('bump') || text.includes('fist')) return 'Fist my bump! Amaze!';
  if (text.includes('hello') || text.includes('hi') || text.includes('rocky'))
    return 'Hello Grace! What do we do next? Amaze!';
  return `Good, good, good. I understand: "${userMsg}". Fist my bump! Amaze!`;
};

// ─── Component ────────────────────────────────────────────────────────────────

const Index = () => {
  const [messages, setMessages] = useState<MessageType[]>([
    {
      id: '1',
      content: 'Hello Grace. I am Rocky. What are we working on today? Amaze!',
      isUser: false,
      timestamp: new Date(),
    },
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [attachedFile, setAttachedFile] = useState<AttachedFile | null>(null);
  const [uploadedVideos, setUploadedVideos] = useState<UploadedVideo[]>([]);
  const [activeVideo, setActiveVideo] = useState<UploadedVideo | null>(null);
  const [isProcessingVideo, setIsProcessingVideo] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  // Persist conversation thread_id so the LangGraph checkpointer keeps memory
  // across turns. Loaded from localStorage on first mount; saved whenever it
  // changes. A new ID is written back by the server on the first turn.
  const [threadId, setThreadId] = useState<string | null>(() => {
    try {
      return localStorage.getItem(THREAD_ID_KEY);
    } catch {
      return null;
    }
  });

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  // Persist thread_id whenever it changes
  useEffect(() => {
    try {
      if (threadId) {
        localStorage.setItem(THREAD_ID_KEY, threadId);
      } else {
        localStorage.removeItem(THREAD_ID_KEY);
      }
    } catch {
      // Storage may be unavailable (private browsing, quota exceeded) — silently ignore
    }
  }, [threadId]);

  // Auto-select the last completed video when none is active
  useEffect(() => {
    if (!activeVideo && uploadedVideos.length > 0) {
      const lastCompleted = [...uploadedVideos]
        .reverse()
        .find((v) => v.processingStatus === 'completed');
      if (lastCompleted) setActiveVideo(lastCompleted);
    }
  }, [uploadedVideos, activeVideo]);

  // ── Poll task status for in-progress videos ──────────────────────────────
  const polledIds = useRef<Set<string>>(new Set());

  const pollTaskStatus = useCallback(
    async (video: UploadedVideo) => {
      if (!video.taskId || polledIds.current.has(video.id)) return;
      polledIds.current.add(video.id);

      const MAX_POLLS = 120; // max 10 min at 5 s intervals
      let polls = 0;

      const interval = setInterval(async () => {
        polls++;
        if (polls > MAX_POLLS) {
          clearInterval(interval);
          polledIds.current.delete(video.id);
          setUploadedVideos((prev) =>
            prev.map((v) =>
              v.id === video.id ? { ...v, processingStatus: 'failed' } : v,
            ),
          );
          toast.error(`Processing timed out for "${video.file.name}".`);
          return;
        }

        try {
          const data = await getTaskStatus(video.taskId!);
          if (data.status === 'completed' || data.status === 'failed') {
            clearInterval(interval);
            polledIds.current.delete(video.id);
            setUploadedVideos((prev) =>
              prev.map((v) =>
                v.id === video.id ? { ...v, processingStatus: data.status as UploadedVideo['processingStatus'] } : v,
              ),
            );
            if (data.status === 'completed') {
              toast.success(`"${video.file.name}" is ready for querying.`);
            } else {
              toast.error(`Processing failed for "${video.file.name}".`);
            }
          }
        } catch {
          // Network hiccup — keep polling; don't explode
        }
      }, 5_000);
    },
    [],
  );

  // Start polling for any in-progress videos already in state (e.g. after hot reload)
  useEffect(() => {
    uploadedVideos
      .filter((v) => v.processingStatus === 'in_progress' && v.taskId)
      .forEach(pollTaskStatus);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Chat ─────────────────────────────────────────────────────────────────

  const generateAIResponse = async (
    userMessage: string,
    fileUrl?: string,
    fileType?: 'image' | 'video',
  ): Promise<{ message: string; clipPath?: string }> => {
    // Determine which video to attach to this chat turn
    const videoToUse = activeVideo ?? uploadedVideos[uploadedVideos.length - 1] ?? null;

    // Convert attached local image to base64
    let imageBase64: string | undefined;
    if (fileUrl && fileType === 'image') {
      try {
        const res = await fetch(fileUrl);
        const blob = await res.blob();
        imageBase64 = await new Promise<string>((resolve) => {
          const reader = new FileReader();
          reader.onloadend = () => {
            const result = reader.result as string;
            resolve(result.split(',')[1]);
          };
          reader.readAsDataURL(blob);
        });
      } catch {
        // If we can't load the image, proceed without it
      }
    }

    // Normalise the video path to forward slashes (safe on both platforms)
    const videoPath = videoToUse?.videoPath?.replace(/\\/g, '/');

    try {
      const data = await sendChatMessage({
        message: userMessage,
        video_path: videoPath,
        image_base64: imageBase64,
        thread_id: threadId ?? undefined,
      });

      // Persist the thread_id returned by the server for subsequent turns
      if (data.thread_id && data.thread_id !== threadId) {
        setThreadId(data.thread_id);
      }

      return {
        message: data.message,
        clipPath: data.clip_path ?? undefined,
      };
    } catch (err) {
      // Distinguish timeout/network errors from server errors for better user messaging
      if (err instanceof ApiError) {
        if (err.status === 503) {
          toast.warning('Rocky is still waking up. Please give it a moment!');
        } else if (err.status === 0) {
          toast.warning('Backend offline — Rocky is running in offline mode.');
        } else {
          toast.error(`Rocky hit an error (${err.status}): ${err.message}`);
        }
      } else {
        toast.error('Something went wrong connecting to Rocky.');
      }

      // Graceful offline fallback — never leave the UI hanging
      return {
        message: getOfflineRockyResponse(userMessage, fileType === 'image', Boolean(videoToUse)),
      };
    }
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() && !attachedFile) return;

    const fileUrl = attachedFile?.url;
    const fileType = attachedFile?.type;

    const userMessage: MessageType = {
      id: Date.now().toString(),
      content: inputMessage || (fileType === 'image' ? 'Shared an image' : 'Shared a video'),
      isUser: true,
      timestamp: new Date(),
      fileUrl,
      fileType,
    };

    setMessages((prev) => [...prev, userMessage]);
    const currentInput = inputMessage;
    setInputMessage('');
    setAttachedFile(null);
    setIsTyping(true);

    try {
      const aiResponseContent = await generateAIResponse(currentInput, fileUrl, fileType);

      const aiResponse: MessageType = {
        id: (Date.now() + 1).toString(),
        content: aiResponseContent.message,
        isUser: false,
        timestamp: new Date(),
        clipPath: aiResponseContent.clipPath,
      };

      setMessages((prev) => [...prev, aiResponse]);
    } catch (error) {
      console.error('Unexpected error in sendMessage:', error);
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          content: 'Sorry, Grace. Communication error. Please try again.',
          isUser: false,
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  // ── Image attachment ──────────────────────────────────────────────────────

  const handleImageUpload = (file: File) => {
    const fileUrl = URL.createObjectURL(file);
    setAttachedFile({ url: fileUrl, type: 'image', file });
  };

  // ── Video upload & processing pipeline ───────────────────────────────────

  const handleVideoUpload = async (file: File) => {
    setIsProcessingVideo(true);
    setUploadProgress(0);

    const localUrl = URL.createObjectURL(file);

    try {
      // 1. Upload the raw file with real progress tracking (0 → 80 %)
      const uploadData = await uploadVideo(file, (pct) => {
        // Map upload progress to 0–80 % of the overall bar
        setUploadProgress(Math.round(pct * 0.8));
      });

      if (!uploadData.video_path) {
        throw new ApiError(500, 'Server returned no video_path after upload.');
      }

      setUploadProgress(80);

      // 2. Kick off background indexing
      const processData = await processVideo(uploadData.video_path);

      setUploadProgress(90);

      const newVideo: UploadedVideo = {
        id: uploadData.video_path,
        url: localUrl,
        file,
        timestamp: new Date(),
        videoPath: uploadData.video_path,
        taskId: processData.task_id,
        processingStatus: 'in_progress',
      };

      setUploadedVideos((prev) => [...prev, newVideo]);
      setActiveVideo(newVideo);
      setUploadProgress(100);

      // 3. Start polling for completion in the background
      pollTaskStatus(newVideo);

      toast.info(`"${file.name}" uploaded — indexing in background…`);
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Upload failed. Check your connection and try again.';

      toast.error(message);

      // Offline / upload-failed fallback — add the video locally so the user
      // can still see it and attempt to chat (agent will not have it indexed).
      const fallbackVideo: UploadedVideo = {
        id: Date.now().toString(),
        url: localUrl,
        file,
        timestamp: new Date(),
        videoPath: `shared_media/${file.name}`,
        processingStatus: 'failed',
      };

      setUploadedVideos((prev) => [...prev, fallbackVideo]);
      setActiveVideo(fallbackVideo);
    } finally {
      setIsProcessingVideo(false);
      setUploadProgress(0);
    }
  };

  // ── Video selection / removal ─────────────────────────────────────────────

  const selectVideo = (video: UploadedVideo) => {
    setActiveVideo(video);
    setAttachedFile(null);
  };

  const removeVideo = (videoId: string) => {
    const videoToRemove = uploadedVideos.find((v) => v.id === videoId);
    if (videoToRemove) {
      URL.revokeObjectURL(videoToRemove.url);
      setUploadedVideos((prev) => prev.filter((v) => v.id !== videoId));
      if (activeVideo?.id === videoId) setActiveVideo(null);
    }
  };

  // ── Memory reset ──────────────────────────────────────────────────────────

  const handleResetMemory = async () => {
    if (!threadId) {
      toast.info('No active conversation to reset.');
      return;
    }
    try {
      await resetMemory(threadId);
      setThreadId(null);
      setMessages([
        {
          id: Date.now().toString(),
          content: 'Memory cleared. Hello again, Grace! Amaze!',
          isUser: false,
          timestamp: new Date(),
        },
      ]);
      toast.success("Rocky's memory has been reset.");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Failed to reset memory.';
      toast.error(message);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-obsidian-950 text-ink-100 font-mono relative w-full">
      <BackgroundAnimation />

      {/* Main Chat Area with right padding for fixed sidebar */}
      <div className="flex flex-col relative z-10 min-h-screen pr-80 md:pr-96">
        <ChatHeader onResetMemory={handleResetMemory} hasThread={Boolean(threadId)} />

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="max-w-4xl mx-auto space-y-6">
            {messages.map((message) => (
              <Message key={message.id} {...message} />
            ))}

            {isTyping && <TypingIndicator />}

            <div ref={messagesEndRef} />
          </div>
        </div>

        <ChatInput
          inputMessage={inputMessage}
          setInputMessage={setInputMessage}
          attachedFile={attachedFile}
          setAttachedFile={setAttachedFile}
          activeVideo={activeVideo}
          isTyping={isTyping}
          onSendMessage={sendMessage}
          onImageUpload={handleImageUpload}
        />
      </div>

      <VideoSidebar
        uploadedVideos={uploadedVideos}
        activeVideo={activeVideo}
        isProcessingVideo={isProcessingVideo}
        uploadProgress={uploadProgress}
        onVideoUpload={handleVideoUpload}
        onSelectVideo={selectVideo}
        onRemoveVideo={removeVideo}
      />
    </div>
  );
};

export default Index;



