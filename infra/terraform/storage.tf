resource "aws_s3_bucket" "originals" {
  bucket = "${local.name_prefix}-${data.aws_caller_identity.current.account_id}-${var.aws_region}-originals"

  force_destroy = (
    var.environment == "dev"
  )
}


resource "aws_s3_bucket" "media" {
  bucket = "${local.name_prefix}-${data.aws_caller_identity.current.account_id}-${var.aws_region}-media"

  force_destroy = (
    var.environment == "dev"
  )
}


resource "aws_s3_bucket_public_access_block" "originals" {
  bucket = aws_s3_bucket.originals.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}


resource "aws_s3_bucket_public_access_block" "media" {
  bucket = aws_s3_bucket.media.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}


resource "aws_s3_bucket_ownership_controls" "originals" {
  bucket = aws_s3_bucket.originals.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}


resource "aws_s3_bucket_ownership_controls" "media" {
  bucket = aws_s3_bucket.media.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}


resource "aws_s3_bucket_versioning" "originals" {
  bucket = aws_s3_bucket.originals.id

  versioning_configuration {
    status = "Enabled"
  }
}


resource "aws_s3_bucket_versioning" "media" {
  bucket = aws_s3_bucket.media.id

  versioning_configuration {
    status = "Enabled"
  }
}


resource "aws_s3_bucket_server_side_encryption_configuration" "originals" {
  bucket = aws_s3_bucket.originals.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}


resource "aws_s3_bucket_server_side_encryption_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}


resource "aws_s3_bucket_cors_configuration" "originals" {
  bucket = aws_s3_bucket.originals.id

  cors_rule {
    allowed_headers = [
      "*",
    ]

    allowed_methods = [
      "GET",
      "HEAD",
      "POST",
      "PUT",
    ]

    allowed_origins = (
      var.frontend_origins
    )

    expose_headers = [
      "ETag",
    ]

    max_age_seconds = 3600
  }
}


resource "aws_s3_bucket_lifecycle_configuration" "originals" {
  bucket = aws_s3_bucket.originals.id

  rule {
    id     = "cleanup-incomplete-multipart"
    status = "Enabled"

    filter {}


    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}