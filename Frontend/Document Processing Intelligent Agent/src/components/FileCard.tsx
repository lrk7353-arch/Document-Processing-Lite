import React from "react";

interface FileCardProps {
  file: File;
  progress: number;
  status: string;
}

const FileCard: React.FC<FileCardProps> = ({ file, progress, status }) => {
  return (
    <div className="p-4 mt-4 bg-white shadow rounded-lg">
      <h3 className="text-lg font-semibold">{file.name}</h3>
      <p className="text-gray-600">文件类型：{file.type}</p>
      <p className="text-gray-600">上传状态：{status}</p>
      <div className="mt-2">
        <div className="w-full bg-gray-200 h-3 rounded-full mb-3">
          <div
            className="bg-blue-500 h-3 rounded-full"
            style={{ width: `${progress}%` }}
          ></div>
        </div>
        <p className="text-gray-500 text-sm">{progress}% 上传完成</p>
      </div>
    </div>
  );
};

export default FileCard;
