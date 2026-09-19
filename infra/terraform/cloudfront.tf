resource "aws_cloudfront_origin_access_control" "media" {
  name = "${local.name_prefix}-media"

  description = (
    "OAC for Virelai private media bucket"
  )

  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}


resource "aws_cloudfront_response_headers_policy" "media_cors" {
  name = "${local.name_prefix}-media-cors"

  cors_config {
    access_control_allow_credentials = false
    access_control_max_age_sec        = 3600
    origin_override                   = true

    access_control_allow_headers {
      items = [
        "*",
      ]
    }

    access_control_allow_methods {
      items = [
        "GET",
        "HEAD",
        "OPTIONS",
      ]
    }

    access_control_allow_origins {
      items = var.frontend_origins
    }

    access_control_expose_headers {
      items = [
        "ETag",
      ]
    }
  }
}


resource "aws_cloudfront_distribution" "media" {
  enabled         = true
  is_ipv6_enabled = true

  comment = (
    "Virelai ${var.environment} media delivery"
  )

  price_class = "PriceClass_100"

  origin {
    domain_name = (
      aws_s3_bucket.media.bucket_regional_domain_name
    )

    origin_id = "virelai-media-s3"

    origin_access_control_id = (
      aws_cloudfront_origin_access_control.media.id
    )
  }

  default_cache_behavior {
    target_origin_id = "virelai-media-s3"

    viewer_protocol_policy = (
      "redirect-to-https"
    )

    allowed_methods = [
      "GET",
      "HEAD",
      "OPTIONS",
    ]

    cached_methods = [
      "GET",
      "HEAD",
    ]

    compress = true

    # AWS managed CachingOptimized policy.
    cache_policy_id = (
      "658327ea-f89d-4fab-a63d-7e88639e58f6"
    )

    response_headers_policy_id = (
      aws_cloudfront_response_headers_policy
      .media_cors
      .id
    )
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Name = "${local.name_prefix}-media"
  }
}


data "aws_iam_policy_document" "media_cloudfront" {
  statement {
    sid = "AllowCloudFrontReadMedia"

    actions = [
      "s3:GetObject",
    ]

    resources = [
      "${aws_s3_bucket.media.arn}/*",
    ]

    principals {
      type = "Service"

      identifiers = [
        "cloudfront.amazonaws.com",
      ]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"

      values = [
        aws_cloudfront_distribution.media.arn,
      ]
    }
  }
}


resource "aws_s3_bucket_policy" "media_cloudfront" {
  bucket = aws_s3_bucket.media.id

  policy = (
    data.aws_iam_policy_document
    .media_cloudfront
    .json
  )
}