# Multi-stage build for FirstPass Agent
FROM registry.access.redhat.com/ubi9/python-311:latest AS builder

USER 0

# Install build dependencies
WORKDIR /build

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies in a virtual environment
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Final stage
FROM registry.access.redhat.com/ubi9/python-311:latest

USER 0

# Install runtime dependencies
RUN dnf update -y && \
    dnf clean all && \
    rm -rf /var/cache/dnf

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set up application directory
WORKDIR /app

# Copy application code
COPY main.py .
COPY firstpass/ firstpass/
COPY config.yaml .

# Set up permissions for OpenShift compatibility (group 0)
# UBI images already have user 1001, so we just set permissions
RUN chown -R 1001:0 /app && \
    chmod -R g+rwX /app

# Switch to non-root user (using default UID from UBI image)
USER 1001

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command (can be overridden)
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]

# Labels
LABEL name="firstpass-agent" \
      version="0.1.0" \
      description="FirstPass Agent for OpenShift Performance Regression Triage" \
      maintainer="cloud-bulldozer" \
      org.opencontainers.image.source="https://github.com/cloud-bulldozer/firstpass"
