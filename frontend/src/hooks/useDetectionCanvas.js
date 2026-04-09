import { useCallback, useEffect, useRef } from "react";

const HANDLE_SIZE = 8;

function clampBoxToImage(box, imageWidth, imageHeight) {
  const x1 = Math.max(0, Math.min(Number(box.x1), imageWidth));
  const y1 = Math.max(0, Math.min(Number(box.y1), imageHeight));
  const x2 = Math.max(0, Math.min(Number(box.x2), imageWidth));
  const y2 = Math.max(0, Math.min(Number(box.y2), imageHeight));
  return {
    x1: Math.min(x1, x2),
    y1: Math.min(y1, y2),
    x2: Math.max(x1, x2),
    y2: Math.max(y1, y2),
  };
}

function getHandleHit(imagePoint, draftDetection) {
  if (!draftDetection) {
    return null;
  }
  const corners = [
    { key: "nw", x: draftDetection.x1, y: draftDetection.y1 },
    { key: "ne", x: draftDetection.x2, y: draftDetection.y1 },
    { key: "sw", x: draftDetection.x1, y: draftDetection.y2 },
    { key: "se", x: draftDetection.x2, y: draftDetection.y2 },
  ];
  for (const corner of corners) {
    if (Math.abs(imagePoint.x - corner.x) <= HANDLE_SIZE && Math.abs(imagePoint.y - corner.y) <= HANDLE_SIZE) {
      return corner.key;
    }
  }
  return null;
}

function isInsideDraft(imagePoint, draftDetection) {
  if (!draftDetection) {
    return false;
  }
  return (
    imagePoint.x >= draftDetection.x1 &&
    imagePoint.x <= draftDetection.x2 &&
    imagePoint.y >= draftDetection.y1 &&
    imagePoint.y <= draftDetection.y2
  );
}

function getImagePoint(event, canvasElement, imageElement) {
  const rect = canvasElement.getBoundingClientRect();
  const clickX = event.clientX - rect.left;
  const clickY = event.clientY - rect.top;
  return {
    x: clickX / (imageElement.clientWidth / imageElement.naturalWidth),
    y: clickY / (imageElement.clientHeight / imageElement.naturalHeight),
  };
}

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
  isDrawingBox,
  draftDetection,
  onDraftDetectionChange,
}) {
  const detailImageRef = useRef(null);
  const detailCanvasRef = useRef(null);
  const interactionRef = useRef({
    mode: null,
    origin: null,
    draftAtStart: null,
  });

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
    const scaleX = displayWidth / imageElement.naturalWidth;
    const scaleY = displayHeight / imageElement.naturalHeight;

    if (bboxVisible) {
      for (const detection of detailDetections) {
        if (detection.is_deleted || (detection.confidence_score != null && Number(detection.confidence_score) < thresholdValue)) {
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

        const confidence = Number(detection.confidence_score);
        const label = Number.isFinite(confidence)
          ? `${detection.class_name} ${(confidence * 100).toFixed(0)}%`
          : `${detection.class_name} manual`;
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
    }

    if (draftDetection) {
      const x = draftDetection.x1 * scaleX;
      const y = draftDetection.y1 * scaleY;
      const width = (draftDetection.x2 - draftDetection.x1) * scaleX;
      const height = (draftDetection.y2 - draftDetection.y1) * scaleY;
      context.strokeStyle = "#f59e0b";
      context.setLineDash([6, 4]);
      context.lineWidth = 2;
      context.strokeRect(x, y, width, height);
      context.setLineDash([]);

      const handlePoints = [
        { x, y },
        { x: x + width, y },
        { x, y: y + height },
        { x: x + width, y: y + height },
      ];
      context.fillStyle = "#f59e0b";
      for (const point of handlePoints) {
        context.fillRect(point.x - HANDLE_SIZE / 2, point.y - HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE);
      }
    }
  }, [
    bboxVisible,
    currentRun,
    detailDetections,
    detailImage,
    draftDetection,
    isImageDetailVisible,
    thresholdValue,
  ]);

  useEffect(() => {
    drawBoundingBoxes();
  }, [drawBoundingBoxes]);

  useEffect(() => {
    const handleResize = () => {
      drawBoundingBoxes();
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [drawBoundingBoxes]);

  const onCanvasClick = useCallback((event) => {
    if (!detailImage || !currentRun || isDrawingBox || draftDetection) {
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
      if (detection.is_deleted || (detection.confidence_score != null && Number(detection.confidence_score) < thresholdValue)) {
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
  }, [currentRun, detailDetections, detailImage, draftDetection, isDrawingBox, onDetectionHit, thresholdValue]);

  const onCanvasMouseDown = useCallback((event) => {
    if (!detailImage || !currentRun) {
      return;
    }
    const canvas = detailCanvasRef.current;
    const imageElement = detailImageRef.current;
    if (!canvas || !imageElement || !imageElement.naturalWidth || !imageElement.naturalHeight) {
      return;
    }

    const imagePoint = getImagePoint(event, canvas, imageElement);

    if (isDrawingBox && !draftDetection) {
      interactionRef.current = {
        mode: "create",
        origin: imagePoint,
        draftAtStart: null,
      };
      onDraftDetectionChange({
        x1: imagePoint.x,
        y1: imagePoint.y,
        x2: imagePoint.x,
        y2: imagePoint.y,
      });
      return;
    }

    if (!draftDetection) {
      return;
    }

    const handle = getHandleHit(imagePoint, draftDetection);
    if (handle) {
      interactionRef.current = {
        mode: `resize-${handle}`,
        origin: imagePoint,
        draftAtStart: { ...draftDetection },
      };
      return;
    }

    if (isInsideDraft(imagePoint, draftDetection)) {
      interactionRef.current = {
        mode: "move",
        origin: imagePoint,
        draftAtStart: { ...draftDetection },
      };
    }
  }, [currentRun, detailImage, draftDetection, isDrawingBox, onDraftDetectionChange]);

  const onCanvasMouseMove = useCallback((event) => {
    const imageElement = detailImageRef.current;
    const canvas = detailCanvasRef.current;
    const interaction = interactionRef.current;
    if (!imageElement || !canvas || !interaction.mode) {
      return;
    }

    const imagePoint = getImagePoint(event, canvas, imageElement);
    const imageWidth = imageElement.naturalWidth;
    const imageHeight = imageElement.naturalHeight;

    if (interaction.mode === "create" && interaction.origin) {
      onDraftDetectionChange(
        clampBoxToImage(
          {
            x1: interaction.origin.x,
            y1: interaction.origin.y,
            x2: imagePoint.x,
            y2: imagePoint.y,
          },
          imageWidth,
          imageHeight,
        ),
      );
      return;
    }

    if (!interaction.draftAtStart || !interaction.origin) {
      return;
    }

    const deltaX = imagePoint.x - interaction.origin.x;
    const deltaY = imagePoint.y - interaction.origin.y;
    const nextDraft = { ...interaction.draftAtStart };

    if (interaction.mode === "move") {
      const width = interaction.draftAtStart.x2 - interaction.draftAtStart.x1;
      const height = interaction.draftAtStart.y2 - interaction.draftAtStart.y1;
      const x1 = Math.max(0, Math.min(interaction.draftAtStart.x1 + deltaX, imageWidth - width));
      const y1 = Math.max(0, Math.min(interaction.draftAtStart.y1 + deltaY, imageHeight - height));
      onDraftDetectionChange({
        x1,
        y1,
        x2: x1 + width,
        y2: y1 + height,
      });
      return;
    }

    if (interaction.mode === "resize-nw") {
      nextDraft.x1 += deltaX;
      nextDraft.y1 += deltaY;
    } else if (interaction.mode === "resize-ne") {
      nextDraft.x2 += deltaX;
      nextDraft.y1 += deltaY;
    } else if (interaction.mode === "resize-sw") {
      nextDraft.x1 += deltaX;
      nextDraft.y2 += deltaY;
    } else if (interaction.mode === "resize-se") {
      nextDraft.x2 += deltaX;
      nextDraft.y2 += deltaY;
    }

    onDraftDetectionChange(clampBoxToImage(nextDraft, imageWidth, imageHeight));
  }, [onDraftDetectionChange]);

  const onCanvasMouseUp = useCallback(() => {
    interactionRef.current = {
      mode: null,
      origin: null,
      draftAtStart: null,
    };
  }, []);

  return {
    detailImageRef,
    detailCanvasRef,
    drawBoundingBoxes,
    onCanvasClick,
    onCanvasMouseDown,
    onCanvasMouseMove,
    onCanvasMouseUp,
  };
}

export default useDetectionCanvas;
