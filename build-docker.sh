#!/bin/bash
# Build script for Docker deployment

set -e

echo "Building redact-clinical-german Docker image..."

# Build the Docker image
docker build -t redact-clinical-german:latest .

echo "✓ Docker image built successfully"
echo ""
echo "To test the image, run:"
echo "  docker run -v \$(pwd)/input:/input -v \$(pwd)/output:/output \\"
echo "    redact-clinical-german /input/test.pdf --output /output/anonymized.pdf"
echo ""
echo "To tag for a registry:"
echo "  docker tag redact-clinical-german:latest your-registry/redact-clinical-german:1.0.0"
echo "  docker push your-registry/redact-clinical-german:1.0.0"
