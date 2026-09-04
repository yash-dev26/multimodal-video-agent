import { useRef } from 'react';
import { Send, Image, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

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
}

interface ChatInputProps {
  inputMessage: string;
  setInputMessage: (message: string) => void;
  attachedFile: AttachedFile | null;
  setAttachedFile: (file: AttachedFile | null) => void;
  activeVideo: UploadedVideo | null;
  isTyping: boolean;
  onSendMessage: () => void;
  onImageUpload: (file: File) => void;
}

const ChatInput = ({
  inputMessage,
  setInputMessage,
  attachedFile,
  setAttachedFile,
  activeVideo,
  isTyping,
  onSendMessage,
  onImageUpload,
}: ChatInputProps) => {
  const imageInputRef = useRef<HTMLInputElement>(null);

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      onSendMessage();
    }
  };

  const handleImageAttach = () => {
    imageInputRef.current?.click();
  };

  const handleImageUploadInternal = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onImageUpload(file);
    }
    e.target.value = '';
  };

  const removeAttachedFile = () => {
    if (attachedFile) {
      URL.revokeObjectURL(attachedFile.url);
      setAttachedFile(null);
    }
  };

  return (
    <div className="glass-panel border-x-0 border-b-0 p-4">
      {/* File Preview - Only for images */}
      {attachedFile && (
        <div className="max-w-4xl mx-auto mb-3">
          <div className="relative inline-block glass-panel-raised rounded-lg p-2">
            <div className="flex items-center space-x-2">
              <img
                src={attachedFile.url}
                alt="Preview"
                className="w-12 h-12 object-cover rounded border border-gold-500/25"
              />
              <span className="text-sm text-ink-100 font-mono">
                {attachedFile.file.name}
              </span>
              <Button
                onClick={removeAttachedFile}
                size="icon"
                variant="default"
                className="w-6 h-6"
              >
                <X className="w-3 h-3" />
              </Button>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-4xl mx-auto flex items-center space-x-2">
        <Button onClick={handleImageAttach} variant="secondary" size="icon">
          <Image className="w-4 h-4" />
        </Button>
        <Input
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyDown={handleKeyPress}
          placeholder="Enter your message, Grace..."
          className="flex-1"
          disabled={isTyping}
        />
        <Button
          onClick={onSendMessage}
          disabled={(!inputMessage.trim() && !attachedFile) || isTyping}
          variant="default"
        >
          <Send className="w-4 h-4" />
        </Button>
      </div>

      {/* Hidden file input */}
      <input
        ref={imageInputRef}
        type="file"
        accept="image/*"
        onChange={handleImageUploadInternal}
        style={{ display: 'none' }}
      />

      <div className="max-w-4xl mx-auto mt-2">
        <p className="text-xs text-ink-600 text-center font-mono tracking-wide">
          System operational — amaze!
        </p>
      </div>
    </div>
  );
};

export default ChatInput;
