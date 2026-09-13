import { Button } from '@/components/ui/button';
import { AlertCircle, CheckCircle, Loader2, Play, Upload, X } from 'lucide-react';
import { useRef } from 'react';

interface UploadedVideo {
  id: string;
  url: string;
  file: File;
  timestamp: Date;
  videoPath?: string;
  taskId?: string;
  processingStatus?: 'pending' | 'in_progress' | 'completed' | 'failed';
}

interface VideoSidebarProps {
  uploadedVideos: UploadedVideo[];
  activeVideo: UploadedVideo | null;
  isProcessingVideo: boolean;
  uploadProgress: number;
  onVideoUpload: (file: File) => void;
  onSelectVideo: (video: UploadedVideo) => void;
  onRemoveVideo: (videoId: string) => void;
}

const VideoSidebar = ({
  uploadedVideos,
  activeVideo,
  isProcessingVideo,
  uploadProgress,
  onVideoUpload,
  onSelectVideo,
  onRemoveVideo,
}: VideoSidebarProps) => {
  const videoInputRef = useRef<HTMLInputElement>(null);

  const handleVideoUpload = () => {
    if (videoInputRef.current) {
      videoInputRef.current.click();
    } else {
      console.error('VideoSidebar - videoInputRef is null!');
    }
  };

  const handleVideoFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onVideoUpload(file);
    }
    e.target.value = '';
  };

  const handleVideoClick = (video: UploadedVideo, videoElement: HTMLVideoElement) => {
    onSelectVideo(video);

    if (videoElement.paused) {
      uploadedVideos.forEach((v) => {
        const otherVideo = document.getElementById(`video-${v.id}`) as HTMLVideoElement;
        if (otherVideo && otherVideo !== videoElement && !otherVideo.paused) {
          otherVideo.pause();
        }
      });
      videoElement.play().catch((err) => console.log('Playback interrupted:', err));
    } else {
      videoElement.pause();
    }
  };

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'in_progress':
        return <Loader2 className="w-4 h-4 text-gold-300 animate-spin" />;
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-emerald-400" />;
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-400" />;
      default:
        return null;
    }
  };

  const getStatusText = (status?: string) => {
    switch (status) {
      case 'in_progress':
        return 'Processing…';
      case 'completed':
        return 'Ready';
      case 'failed':
        return 'Failed';
      default:
        return '';
    }
  };

  return (
    <div className="fixed right-0 top-0 w-80 md:w-96 h-screen glass-panel border-y-0 border-r-0 flex flex-col z-20 font-mono">
      <div className="p-4 gold-hairline border-b">
        <h3 className="text-xl font-display font-semibold text-gold-300 mb-3 text-center tracking-wide">
          Video Library
        </h3>
        <Button
          onClick={handleVideoUpload}
          className="w-full text-xs"
          size="sm"
          disabled={isProcessingVideo}
        >
          {isProcessingVideo ? (
            <div className="flex items-center space-x-2">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>Processing…</span>
            </div>
          ) : (
            <div className="flex items-center space-x-2">
              <Upload className="w-3 h-3" />
              <span>Upload video</span>
            </div>
          )}
        </Button>

        {isProcessingVideo && (
          <div className="mt-4 p-4 glass-panel-raised rounded-lg">
            <div className="flex flex-col items-center space-y-3">
              <Loader2 className="w-8 h-8 text-gold-400 animate-spin" />

              <div className="text-center">
                <div className="text-sm text-gold-300 font-semibold tracking-wide">Processing</div>
                <div className="text-xs text-ink-400 mt-1">Please wait…</div>
              </div>

              {uploadProgress > 0 && (
                <div className="w-full bg-obsidian-800 rounded-full h-1.5">
                  <div
                    className="bg-gradient-to-r from-gold-500 to-gold-300 h-1.5 rounded-full transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  ></div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {uploadedVideos.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center px-6 text-center">
            <p className="text-sm font-semibold text-gold-300">No videos yet</p>
            <p className="mt-2 text-xs leading-relaxed text-ink-500">
              Upload a video to start analyzing, searching, or chatting with Rocky.
            </p>
          </div>
        )}

        {uploadedVideos.map((video) => {
          const isActive = activeVideo?.id === video.id;
          const isProcessing = video.processingStatus === 'in_progress';
          const isFailed = video.processingStatus === 'failed';

          return (
            <div key={video.id} className="relative group">
              <div
                className={`relative aspect-video rounded-md overflow-hidden border transition-colors duration-200 ${
                  isActive
                    ? 'border-gold-400 shadow-glow-gold-sm'
                    : isFailed
                    ? 'border-red-400/40'
                    : 'border-ink-700 group-hover:border-gold-400/50'
                }`}
              >
                <video
                  id={`video-${video.id}`}
                  src={video.url}
                  className={`w-full h-full object-cover cursor-pointer transition-opacity duration-200 ${
                    isActive ? '' : 'opacity-80 group-hover:opacity-100'
                  }`}
                  onClick={(e) => handleVideoClick(video, e.currentTarget)}
                />

                {isProcessing && (
                  <div className="absolute inset-0 flex items-center justify-center bg-obsidian-950/75">
                    <div className="text-center">
                      <Loader2 className="w-6 h-6 text-gold-300 animate-spin mx-auto mb-1.5" />
                      <div className="text-[11px] text-gold-200">Processing…</div>
                    </div>
                  </div>
                )}

                {!isProcessing && (
                  <div
                    className="absolute inset-0 flex items-center justify-center bg-obsidian-950/40 cursor-pointer opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={(e) => {
                      e.stopPropagation();
                      const videoElement = document.getElementById(
                        `video-${video.id}`
                      ) as HTMLVideoElement;
                      if (videoElement) {
                        handleVideoClick(video, videoElement);
                      }
                    }}
                  >
                    <div className="bg-gold-400 rounded-full p-2">
                      <Play className="w-4 h-4 text-obsidian-950 fill-obsidian-950 ml-0.5" />
                    </div>
                  </div>
                )}

                <Button
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemoveVideo(video.id);
                  }}
                  size="icon"
                  variant="secondary"
                  className="absolute top-1 right-1 w-6 h-6 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <X className="w-3 h-3" />
                </Button>
              </div>

              <div className="px-1 mt-1.5">
                <div className="flex items-center justify-between">
                  <p className="text-xs text-ink-100 truncate flex-1">{video.file.name}</p>
                  {getStatusIcon(video.processingStatus)}
                </div>
                <div className="flex items-center justify-between mt-0.5">
                  <p className="text-xs text-ink-600">
                    {video.timestamp.toLocaleTimeString()}
                  </p>
                  {video.processingStatus && (
                    <p
                      className={`text-xs ${
                        video.processingStatus === 'completed'
                          ? 'text-emerald-400'
                          : video.processingStatus === 'failed'
                          ? 'text-red-400'
                          : 'text-gold-300'
                      }`}
                    >
                      {getStatusText(video.processingStatus)}
                    </p>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <input
        ref={videoInputRef}
        type="file"
        accept="video/*"
        onChange={handleVideoFileUpload}
        style={{ display: 'none' }}
      />
    </div>
  );
};

export default VideoSidebar;