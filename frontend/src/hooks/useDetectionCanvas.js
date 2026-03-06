import { useCallback, useEffect, useRef } from "react";

/**
 * Handles drawing boxes on the image and detecting box clicks.
 */
function useDetectionCanvas({
  isImageDetailVisible,
  currentRun,
  detailImage,
  detailDetections,
  thresholdValue,
  bboxVisible,
  onDetectionHit,
}) {
  const detailImageRef = useRef(null);
  const detailCanvasRef = useRef(null);

  // Draw detection boxes and labels on top of the image.
  const drawBoundingBoxes = useCallback(() => {
    if (!isImageDetailVisible || !detailImage || !currentRun) {
      return;
    }

    const imageElement = detailImageRef.current;
    const canvasElement = detailCanvasRef.current;
    if (!imageElement || !canvasElement || !imageElement.naturalWidth || !imageElement.naturalHeight) {
      return;
    }

    const displayWidth = imageElement.clientWidth;
    const displayHeight = imageElement.clientHeight;
    canvasElement.width = displayWidth;
    canvasElement.height = displayHeight;

    const context = canvasElement.getContext("2d");
    context.clearRect(0, 0, canvasElement.width, canvasElement.height);

    if (!bboxVisible) {
      return;
    }

    const scaleX = displayWidth / imageElement.naturalWidth;
    const scaleY = displayHeight / imageElement.naturalHeight;

    for (const detection of detailDetections) {
      if (detection.is_deleted || Number(detection.confidence_score) < thresholdValue) {
        continue;
      }

      const x = Number(detection.bbox_x1) * scaleX;
      const y = Number(detection.bbox_y1) * scaleY;
      const width = (Number(detection.bbox_x2) - Number(detection.bbox_x1)) * scaleX;
      const height = (Number(detection.bbox_y2) - Number(detection.bbox_y1)) * scaleY;

      const color = detection.class_name === "live" ? "#22c55e" : "#ef4444";
      context.strokeStyle = color;
      context.lineWidth = 2;
      context.strokeRect(x, y, width, height);

      const label = `${detection.class_name} ${(Number(detection.confidence_score) * 100).toFixed(0)}%`;
      context.font = "600 11px 'Geist', sans-serif";
      const textMetrics = context.measureText(label);
      const textHeight = 16;
      const padding = 4;
      const labelY = y > textHeight + 4 ? y - textHeight - 2 : y + height + 2;

      context.fillStyle = "rgba(0,0,0,0.7)";
      context.fillRect(x, labelY, textMetrics.width + padding * 2, textHeight);

      context.fillStyle = "#fff";
      context.fillText(label, x + padding, labelY + 12);
    }
  }, [bboxVisible, currentRun, detailDetections, detailImage, isImageDetailVisible, thresholdValue]);

  // Redraw whenever source data or visibility state changes.
  useEffect(() => {
    drawBoundingBoxes();
  }, [drawBoundingBoxes]);

  // Redraw when window size changes so boxes still line up with the image.
  useEffect(() => {
    const handleResize = () => {
      drawBoundingBoxes();
    };

    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, [drawBoundingBoxes]);

  // Convert click position to image coordinates and find the clicked box.
  const onCanvasClick = useCallback((event) => {
    if (!detailImage || !currentRun) {
      return;
    }

    const canvas = detailCanvasRef.current;
    const imageElement = detailImageRef.current;
    if (!canvas || !imageElement) {
      return;
    }

    const rect = canvas.getBoundingClientRect();
    const clickX = event.clientX - rect.left;
    const clickY = event.clientY - rect.top;

    const scaleX = imageElement.clientWidth / imageElement.naturalWidth;
    const scaleY = imageElement.clientHeight / imageElement.naturalHeight;

    for (const detection of detailDetections) {
      if (detection.is_deleted || Number(detection.confidence_score) < thresholdValue) {
        continue;
      }

      const x1 = Number(detection.bbox_x1) * scaleX;
      const y1 = Number(detection.bbox_y1) * scaleY;
      const x2 = Number(detection.bbox_x2) * scaleX;
      const y2 = Number(detection.bbox_y2) * scaleY;

      if (clickX >= x1 && clickX <= x2 && clickY >= y1 && clickY <= y2) {
        onDetectionHit(detection);
        return;
      }
    }
  }, [currentRun, detailDetections, detailImage, onDetectionHit, thresholdValue]);

  return {
    detailImageRef,
    detailCanvasRef,
    drawBoundingBoxes,
    onCanvasClick,
  };
}

export default useDetectionCanvas;
