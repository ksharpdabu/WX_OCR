"""Flatten annotations into real image pixels; history never enters the export."""
from dataclasses import dataclass
import math

from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPainterPathStroker, QPen, QPolygonF


@dataclass(frozen=True)
class Annotation:
    kind: str
    points: tuple[tuple[float, float], ...]
    color: str = '#ff4d4f'
    width: float = 4
    text: str = ''
    font_size: int = 20


def _path(points):
    path = QPainterPath(QPointF(*points[0]))
    for point in points[1:]:
        path.lineTo(QPointF(*point))
    return path


class AnnotationDocument:
    def __init__(self, image: QImage, logical_size: QSizeF):
        if image.isNull() or logical_size.width() <= 0 or logical_size.height() <= 0:
            raise ValueError('截图区域不能为空')
        self.original = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied).copy()
        self.original.setDevicePixelRatio(1)
        self.logical_size = QSizeF(logical_size)
        self._image = self.original.copy()
        self.actions = []

    def render(self, pending=None):
        return self._apply(self._image, pending) if pending else QImage(self._image)

    def commit(self, annotation):
        if not annotation.points or (annotation.kind == 'text' and not annotation.text.strip()):
            return
        self._image = self._apply(self._image, annotation)
        self.actions.append(annotation)

    def undo(self):
        if not self.actions:
            return
        self.actions.pop()
        self._image = self.original.copy()
        for action in self.actions:
            self._image = self._apply(self._image, action)

    def _apply(self, source, annotation):
        image = source.copy()
        sx = image.width() / self.logical_size.width()
        sy = image.height() / self.logical_size.height()
        p = QPainter(image)
        try:
            p.scale(sx, sy)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(QPen(QColor(annotation.color), annotation.width,
                         Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            points = annotation.points
            if annotation.kind == 'pen':
                if len(points) == 1:
                    p.setBrush(QColor(annotation.color))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawEllipse(QPointF(*points[0]), annotation.width/2, annotation.width/2)
                else:
                    p.drawPath(_path(points))
            elif annotation.kind == 'rect':
                p.drawRect(QRectF(QPointF(*points[0]), QPointF(*points[-1])).normalized())
            elif annotation.kind == 'arrow':
                a, b = QPointF(*points[0]), QPointF(*points[-1])
                distance = math.hypot(b.x()-a.x(), b.y()-a.y())
                if distance > 0:
                    p.drawLine(a, b)
                    angle = math.atan2(b.y()-a.y(), b.x()-a.x())
                    length = min(max(12, annotation.width*4), distance)
                    sides = [QPointF(b.x()-length*math.cos(angle+offset),
                                     b.y()-length*math.sin(angle+offset)) for offset in (-0.45, 0.45)]
                    p.setBrush(QColor(annotation.color))
                    p.drawPolygon(QPolygonF([b, *sides]))
            elif annotation.kind == 'mosaic':
                brush_width = annotation.width * 5
                if len(points) == 1:
                    mask = QPainterPath()
                    mask.addEllipse(QPointF(*points[0]), brush_width/2, brush_width/2)
                else:
                    stroker = QPainterPathStroker()
                    stroker.setWidth(brush_width)
                    stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
                    stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    mask = stroker.createStroke(_path(points))
                # Anchor the coarse grid to the whole image so overlapping
                # strokes remain consistent. Clip it to the hand-painted mask.
                block = 12
                coarse = source.scaled(max(1, math.ceil(image.width()/(block*sx))),
                                       max(1, math.ceil(image.height()/(block*sy))),
                                       Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                coarse = coarse.scaled(image.size(), Qt.AspectRatioMode.IgnoreAspectRatio,
                                       Qt.TransformationMode.FastTransformation)
                p.setClipPath(mask)
                p.drawImage(QRectF(QPointF(0, 0), self.logical_size), coarse)
            elif annotation.kind == 'text':
                font = QFont()
                font.setPixelSize(annotation.font_size)
                p.setFont(font)
                x, y = points[0]
                p.drawText(QRectF(x, y, self.logical_size.width()-x, self.logical_size.height()-y),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                           annotation.text)
        finally:
            p.end()
        return image
