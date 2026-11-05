/**
 * Componente Canvas de Firma Digital Táctil y Ratón
 * Optimizado para Smartphones, Tablets y PC
 */
class SmoothSignaturePad {
  constructor(canvasElement, placeholderElement) {
    this.canvas = canvasElement;
    this.placeholder = placeholderElement;
    this.ctx = canvasElement.getContext('2d');
    this.isDrawing = false;
    this.hasDrawn = false;
    this.points = [];

    this.initCanvas();
    this.bindEvents();
  }

  initCanvas() {
    // Ajustar resolución retina / alta densidad
    const rect = this.canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.ctx.scale(dpr, dpr);

    this.ctx.strokeStyle = '#0f172a';
    this.ctx.lineWidth = 2.2;
    this.ctx.lineCap = 'round';
    this.ctx.lineJoin = 'round';
  }

  resize() {
    if (!this.hasDrawn) {
      this.initCanvas();
    }
  }

  getPos(e) {
    const rect = this.canvas.getBoundingClientRect();
    let clientX, clientY;
    if (e.touches && e.touches.length > 0) {
      clientX = e.touches[0].clientX;
      clientY = e.touches[0].clientY;
    } else {
      clientX = e.clientX;
      clientY = e.clientY;
    }
    return {
      x: clientX - rect.left,
      y: clientY - rect.top
    };
  }

  bindEvents() {
    const start = (e) => {
      e.preventDefault();
      this.isDrawing = true;
      this.hasDrawn = true;
      if (this.placeholder) {
        this.placeholder.style.display = 'none';
      }
      const pos = this.getPos(e);
      this.points = [pos];
      this.ctx.beginPath();
      this.ctx.moveTo(pos.x, pos.y);
    };

    const move = (e) => {
      if (!this.isDrawing) return;
      e.preventDefault();
      const pos = this.getPos(e);
      this.points.push(pos);

      if (this.points.length > 2) {
        const lastTwo = this.points.slice(-2);
        const controlPoint = lastTwo[0];
        const endPoint = {
          x: (controlPoint.x + pos.x) / 2,
          y: (controlPoint.y + pos.y) / 2
        };
        this.ctx.quadraticCurveTo(controlPoint.x, controlPoint.y, endPoint.x, endPoint.y);
        this.ctx.stroke();
      } else {
        this.ctx.lineTo(pos.x, pos.y);
        this.ctx.stroke();
      }
    };

    const end = (e) => {
      if (!this.isDrawing) return;
      e.preventDefault();
      this.isDrawing = false;
      this.ctx.closePath();
    };

    // Eventos Mouse
    this.canvas.addEventListener('mousedown', start);
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', end);

    // Eventos Táctiles (Mobile & Tablet)
    this.canvas.addEventListener('touchstart', start, { passive: false });
    this.canvas.addEventListener('touchmove', move, { passive: false });
    this.canvas.addEventListener('touchend', end, { passive: false });
  }

  clear() {
    const dpr = window.devicePixelRatio || 1;
    this.ctx.clearRect(0, 0, this.canvas.width / dpr, this.canvas.height / dpr);
    this.hasDrawn = false;
    this.points = [];
    if (this.placeholder) {
      this.placeholder.style.display = 'block';
    }
  }

  isEmpty() {
    return !this.hasDrawn;
  }

  toDataURL() {
    if (!this.hasDrawn) return null;
    return this.canvas.toDataURL('image/png');
  }
}

window.SmoothSignaturePad = SmoothSignaturePad;

