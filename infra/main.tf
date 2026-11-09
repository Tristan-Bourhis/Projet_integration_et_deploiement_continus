terraform {
  required_version = ">= 1.6, < 2.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.94"
    }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = "transaction-pipeline" }
  }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_vpc" "pipeline" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
}

resource "aws_internet_gateway" "pipeline" {
  vpc_id = aws_vpc.pipeline.id
}

resource "aws_subnet" "pipeline" {
  vpc_id                  = aws_vpc.pipeline.id
  cidr_block              = "10.42.1.0/24"
  map_public_ip_on_launch = true
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.pipeline.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.pipeline.id
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.pipeline.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "pipeline" {
  name_prefix = "transaction-pipeline-"
  description = "SSH restreint ; PostgreSQL et S3 ne sont pas publics"
  vpc_id      = aws_vpc.pipeline.id
  ingress {
    description = "SSH depuis les reseaux explicites d'administration et de CI"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_allowed_cidrs
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_key_pair" "deploy" {
  key_name_prefix = "transaction-pipeline-"
  public_key      = var.ssh_public_key
}

resource "aws_instance" "pipeline" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.pipeline.id
  vpc_security_group_ids      = [aws_security_group.pipeline.id]
  key_name                    = aws_key_pair.deploy.key_name
  user_data                   = file("${path.module}/cloud-init.sh")
  user_data_replace_on_change = true
  depends_on                  = [aws_route_table_association.public]

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }
  root_block_device {
    volume_size = 30
    volume_type = "gp3"
    encrypted   = true
  }
  tags = { Name = "transaction-pipeline" }
}

resource "aws_eip" "pipeline" {
  domain     = "vpc"
  instance   = aws_instance.pipeline.id
  depends_on = [aws_internet_gateway.pipeline]
}
