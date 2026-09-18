output "aws_region" {
  value = var.aws_region
}


output "vpc_id" {
  value = aws_vpc.main.id
}


output "public_subnet_ids" {
  value = [
    for subnet
    in aws_subnet.public :
    subnet.id
  ]
}


output "private_subnet_ids" {
  value = [
    for subnet
    in aws_subnet.private :
    subnet.id
  ]
}


output "originals_bucket" {
  value = aws_s3_bucket.originals.bucket
}


output "media_bucket" {
  value = aws_s3_bucket.media.bucket
}


output "ecr_repository_urls" {
  value = {
    for name, repository
    in aws_ecr_repository.service :
    name => repository.repository_url
  }
}