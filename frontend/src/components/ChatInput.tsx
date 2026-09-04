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
    <div className="border-t border-[#2e231c] bg-[#120f0d] p-4">
      {/* File Preview - Only for images */}
      {attachedFile && (
        <div className="max-w-4xl mx-auto mb-3">
          <div className="relative inline-block bg-[#1a1613] border border-[#382b22] rounded-lg p-2">
            <div className="flex items-center space-x-2">
              <img
                src={attachedFile.url}
                alt="Preview"
                className="w-12 h-12 object-cover rounded border border-[#2e231c]"
              />
              <span className="text-sm text-stone-300 font-mono">
                {attachedFile.file.name}
              </span>
              <Button
                onClick={removeAttachedFile}
                size="icon"
                className="w-6 h-6 bg-[#b48263] hover:bg-[#9e6d50] text-[#120f0d]"
              >
                <X className="w-3 h-3" />
              </Button>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-4xl mx-auto flex items-center space-x-2">
        <Button
          onClick={handleImageAttach}
          className="bg-[#1a1613] hover:bg-[#251f1b] text-stone-300 border border-[#382b22] transition-colors"
          size="icon"
        >
          <Image className="w-4 h-4" />
        </Button>
        <Input
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyDown={handleKeyPress}
          placeholder="Enter your message, Grace..."
          className="flex-1 bg-[#16120f] border-[#382b22] text-stone-100 placeholder-stone-500 font-mono focus-visible:border-[#b48263] focus-visible:ring-[#b48263]"
          disabled={isTyping}
        />
        <Button
          onClick={onSendMessage}
          disabled={(!inputMessage.trim() && !attachedFile) || isTyping}
          className="bg-[#b48263] hover:bg-[#9e6d50] text-[#120f0d] font-bold border-0 transition-colors"
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
        <p className="text-xs text-stone-500 text-center font-mono">
          SYSTEM STATUS: OPERATIONAL | AMAZE!
        </p>
      </div>
    </div>
  );
};

export default ChatInput;
