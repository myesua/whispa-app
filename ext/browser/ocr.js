// OCR module using Tesseract.js
class OCRProcessor {
  constructor() {
    this.worker = null;
    this.workerReady = false;
  }

  // Initialize the OCR processor
  async initialize(progressCallback) {
    try {
      // Create a worker
      if (!this.worker) {
        this.worker = new Worker('tesseract-worker.js');
        
        // Set up message handling from worker
        this.worker.onmessage = (e) => {
          const { type, progress, data, error } = e.data;
          
          if (type === 'progress' && progressCallback) {
            progressCallback(progress);
          } else if (type === 'error') {
            console.error('OCR error:', error);
          }
        };
        
        this.workerReady = true;
      }
      
      return true;
    } catch (error) {
      console.error('Error initializing OCR:', error);
      return false;
    }
  }

  // Process an image and extract text
  async processImage(imageData, options = {}) {
    return new Promise((resolve, reject) => {
      if (!this.workerReady) {
        reject(new Error('OCR worker not initialized'));
        return;
      }
      
      // Set up one-time handler for this specific recognition task
      const messageHandler = (e) => {
        const { type, data, error, success } = e.data;
        
        if (type === 'result') {
          this.worker.removeEventListener('message', messageHandler);
          if (success) {
            resolve(data);
          } else {
            reject(new Error(error || 'OCR processing failed'));
          }
        }
      };
      
      // Add the message handler
      this.worker.addEventListener('message', messageHandler);
      
      // Send the image data to the worker
      this.worker.postMessage({
        imageData,
        options: {
          lang: options.lang || 'eng',
          params: options.params || {}
        }
      });
    });
  }

  // Clean up resources
  terminate() {
    if (this.worker) {
      this.worker.terminate();
      this.worker = null;
      this.workerReady = false;
    }
  }
}

// Export the OCR processor
const ocrProcessor = new OCRProcessor();