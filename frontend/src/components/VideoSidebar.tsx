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
        return <Loader2 className="w-4 h-4 text-[#c59f84] animate-spin" />;
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
        return 'Processing...';
      case 'completed':
        return 'Ready';
      case 'failed':
        return 'Failed';
      default:
        return '';
    }
  };

  return (
    <div className="fixed right-0 top-0 w-80 md:w-96 h-screen border-l border-[#2e231c] bg-[#120f0d] flex flex-col z-20 font-mono">
      <div className="p-4 border-b border-[#2e231c]">
        <h3 className="text-2xl font-bold text-[#c59f84] mb-2 text-center">VIDEO LIBRARY</h3>
        <Button
          onClick={handleVideoUpload}
          className="w-full bg-[#b48263] hover:bg-[#9e6d50] text-[#120f0d] font-bold text-xs"
          size="sm"
          disabled={isProcessingVideo}
        >
          {isProcessingVideo ? (
            <div className="flex items-center space-x-2">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span>Processing...</span>
            </div>
          ) : (
            <div className="flex items-center space-x-2">
              <Upload className="w-3 h-3" />
              <span>Upload Video</span>
            </div>
          )}
        </Button>

        {/* Processing Animation */}
        {isProcessingVideo && (
          <div className="mt-4 p-4 bg-[#1a1411] border border-[#3d2e24] rounded">
            <div className="flex flex-col items-center space-y-3">
              <Loader2 className="w-10 h-10 text-[#b48263] animate-spin" />

              <div className="text-center">
                <div className="text-sm text-[#c59f84] font-bold">PROCESSING</div>
                <div className="text-xs text-stone-400 mt-1">Please wait...</div>
              </div>

              {uploadProgress > 0 && (
                <div className="w-full bg-[#2a221d] rounded-full h-2">
                  <div
                    className="bg-[#b48263] h-2 rounded-full transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  ></div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {uploadedVideos.map((video) => {
          const isActive = activeVideo?.id === video.id;
          const isProcessing = video.processingStatus === 'in_progress';
          const isCompleted = video.processingStatus === 'completed';
          const isFailed = video.processingStatus === 'failed';

          return (
            <div
              key={video.id}
              className={`relative group rounded border transition-colors ${
                isActive
                  ? 'border-[#b48263] bg-[#221a15]'
                  : isFailed
                  ? 'border-red-900 bg-red-950/40'
                  : isCompleted
                  ? 'border-emerald-900/60 bg-[#141b16]'
                  : 'border-[#2e231c] bg-[#181310] hover:border-[#4a392e]'
              }`}
            >
              <div className="aspect-video relative overflow-hidden rounded-t bg-black">
                <video
                  id={`video-${video.id}`}
                  src={video.url}
                  className={`w-full h-full object-cover cursor-pointer transition-all duration-300 ${
                    isActive ? '' : 'grayscale hover:grayscale-0'
                  }`}
                  onClick={(e) => handleVideoClick(video, e.currentTarget)}
                  onPlay={() => console.log(`Video ${video.id} started playing`)}
                  onPause={() => console.log(`Video ${video.id} paused`)}
                />

                {/* Processing overlay */}
                {isProcessing && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/70">
                    <div className="text-center">
                      <Loader2 className="w-8 h-8 text-[#b48263] animate-spin mx-auto mb-2" />
                      <div className="text-xs text-[#c59f84]">Processing...</div>
                    </div>
                  </div>
                )}

                {/* Status overlay */}
                {!isProcessing && (
                  <div
                    className="absolute inset-0 flex items-center justify-center bg-black/40 cursor-pointer opacity-0 group-hover:opacity-100 transition-opacity"
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
                    <div className="bg-[#b48263] rounded-full p-2">
                      <Play className="w-5 h-5 text-[#120f0d] fill-[#120f0d] ml-0.5" />
                    </div>
                  </div>
                )}
              </div>

              <div className="p-2">
                <div className="flex items-center justify-between">
                  <p className="text-xs text-stone-200 truncate flex-1">{video.file.name}</p>
                  {getStatusIcon(video.processingStatus)}
                </div>
                <div className="flex items-center justify-between mt-1">
                  <p className="text-xs text-stone-500">
                    {video.timestamp.toLocaleTimeString()}
                  </p>
                  {video.processingStatus && (
                    <p
                      className={`text-xs ${
                        video.processingStatus === 'completed'
                          ? 'text-emerald-400'
                          : video.processingStatus === 'failed'
                          ? 'text-red-400'
                          : 'text-[#c59f84]'
                      }`}
                    >
                      {getStatusText(video.processingStatus)}
                    </p>
                  )}
                </div>
              </div>

              <Button
                onClick={(e) => {
                  e.stopPropagation();
                  onRemoveVideo(video.id);
                }}
                size="icon"
                className="absolute top-1 right-1 w-6 h-6 bg-[#b48263] hover:bg-[#9e6d50] text-[#120f0d] opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <X className="w-3 h-3" />
              </Button>
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
