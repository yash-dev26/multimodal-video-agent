const TypingIndicator = () => {
  return (
    <div className="flex justify-start animate-fade-in font-mono">
      <div className="max-w-[70%] p-4 rounded-lg bg-[#16120f] border border-[#3d2e24] text-stone-200">
        <div className="text-xs mb-2 text-[#c59f84] font-bold">ROCKY</div>
        <div className="flex items-center space-x-2">
          <div className="flex space-x-1">
            <div className="w-2 h-2 bg-[#b48263] rounded-full animate-bounce"></div>
            <div
              className="w-2 h-2 bg-[#b48263] rounded-full animate-bounce"
              style={{ animationDelay: '0.1s' }}
            ></div>
            <div
              className="w-2 h-2 bg-[#b48263] rounded-full animate-bounce"
              style={{ animationDelay: '0.2s' }}
            ></div>
          </div>
          <span className="text-sm text-stone-300">Processing...</span>
        </div>
      </div>
    </div>
  );
};

export default TypingIndicator;
