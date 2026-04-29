import React, { useRef, useState } from "react";

interface Props {
  onUpload: (file: File) => void;
  onError?: (error: string) => void;
}

const UploadArea: React.FC<Props> = ({ onUpload, onError }) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  
  // 设置文件大小限制（5MB）
  const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB
  
  // 显示错误消息
  const showError = (message: string) => {
    setErrorMessage(message);
    if (onError) {
      onError(message);
    }
    // 3秒后自动清除错误消息
    setTimeout(() => {
      setErrorMessage(null);
    }, 3000);
  };

  const pick = (file: File | null) => {
    if (!file) return;
    
    // 检查文件大小
    if (file.size > MAX_FILE_SIZE) {
      const fileSizeMB = (file.size / (1024 * 1024)).toFixed(2);
      const maxSizeMB = (MAX_FILE_SIZE / (1024 * 1024)).toFixed(0);
      showError(`文件大小过大 (${fileSizeMB}MB)，最大允许 ${maxSizeMB}MB`);
      return;
    }
    
    // 清除之前的错误
    setErrorMessage(null);
    
    // 上传文件
    onUpload(file);
    
    // 选同名文件也能再次触发 onChange
    if (inputRef.current) inputRef.current.value = "";
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    pick(e.target.files?.[0] ?? null);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    pick(e.dataTransfer.files?.[0] ?? null);
  };
  
  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };
  
  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  return (
    <div className="w-full">
      <div
        onClick={() => inputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`flex flex-col items-center justify-center border-2 border-dashed rounded-2xl p-8 transition cursor-pointer select-none
          ${isDragging ? "border-blue-500 bg-blue-50" : "border-blue-300 bg-blue-50 hover:bg-blue-100"}`}
        role="button"
        aria-label="拖拽文件或点击上传"
        tabIndex={0}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
      >
        <p className="text-blue-600 font-medium mb-2">拖拽文件或点击上传</p>
        <p className="text-sm text-gray-500 mb-4">支持 PDF、JPG、PNG、SVG 等格式，最大 5MB</p>
        
        {/* 错误提示 */}
        {errorMessage && (
          <div className="bg-red-50 text-red-600 p-3 rounded-lg text-sm mt-2 mb-2 w-full text-center">
            {errorMessage}
          </div>
        )}

        {/* 双保险隐藏：Tailwind 的 hidden + inline 样式 */}
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png,.svg,.gif,.bmp,.tiff"
          className="hidden"
          style={{ display: "none" }}
          onChange={handleFileChange}
        />
      </div>
    </div>
  );
};

export default UploadArea;
