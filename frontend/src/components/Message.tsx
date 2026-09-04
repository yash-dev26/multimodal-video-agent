import { useState } from 'react';
import { getMediaUrl } from '@/lib/api';

interface MessageProps {
  id: string;
  content: string;
  isUser: boolean;
  timestamp: Date;
  fileUrl?: string;
  fileType?: 'image' | 'video';
  clipPath?: string;
}

const Message = ({ content, isUser, timestamp, fileUrl, fileType, clipPath }: MessageProps) => {
  const [clipError, setClipError] = useState(false);

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in`}>
      <div
        className={`max-w-[700px] w-full p-4 rounded-lg font-mono ${
          isUser
            ? 'bg-[#1e1915] border border-[#382b22] text-stone-100'
            : 'bg-[#16120f] border border-[#3d2e24] text-stone-200'
        }`}
      >
        <div
          className={`flex items-center gap-2 text-xs mb-2 ${
            isUser ? 'text-stone-400' : 'text-[#c59f84]'
          }`}
        >
          {!isUser && (
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 bg-[#b48263] rounded-full"></div>
              <span className="font-bold">ROCKY</span>
            </div>
          )}
          {isUser && <span className="font-bold">GRACE</span>}
        </div>

        {fileUrl && (
          <div className="mb-3">
            {fileType === 'image' ? (
              <img
                src={fileUrl}
                alt="Uploaded"
                className="max-w-full h-auto rounded border border-[#382b22]"
                style={{ maxHeight: '300px' }}
              />
            ) : fileType === 'video' ? (
              <video
                src={fileUrl}
                controls
                className="max-w-full h-auto rounded border border-[#382b22]"
                style={{ maxHeight: '300px' }}
              />
            ) : null}
          </div>
        )}

        {clipPath && (
          <div className="mb-3">
            {clipError ? (
              <div className="flex items-center gap-2 text-xs text-stone-500 border border-[#382b22] rounded p-2">
                <span>⚠</span>
                <span>Clip unavailable — backend may be offline.</span>
              </div>
            ) : (
              <video
                src={getMediaUrl(clipPath)}
                controls
                className="max-w-full h-auto rounded border border-[#382b22]"
                style={{ maxHeight: '300px' }}
                onError={() => setClipError(true)}
              />
            )}
          </div>
        )}

        <p className="leading-relaxed break-words whitespace-pre-line text-sm">{content}</p>
        <div className="text-xs mt-2 opacity-50 text-stone-400">
          {timestamp.toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
};

export default Message;
