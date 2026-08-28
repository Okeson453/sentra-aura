# ------------------------------------------------------------------------------
# SentraAura — Networking Module
# Implements Backend-Infrastructure-DevOps.md §3.1
# VPC with 3 AZs, private subnets, NAT, security groups.
# ------------------------------------------------------------------------------

locals {
  common_tags = merge(var.tags, {
    environment = var.environment
    service     = "networking"
    managed_by  = "terraform"
  })
}

# VPC
resource "aws_vpc" "sentra" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(local.common_tags, {
    Name = "sentra-${var.environment}"
  })
}

# Internet Gateway
resource "aws_internet_gateway" "sentra" {
  vpc_id = aws_vpc.sentra.id
  tags   = merge(local.common_tags, { Name = "sentra-${var.environment}-igw" })
}

# Private subnets
resource "aws_subnet" "private" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.sentra.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone = var.availability_zones[count.index]

  tags = merge(local.common_tags, {
    Name = "sentra-${var.environment}-private-${var.availability_zones[count.index]}"
    Type = "private"
  })
}

# Public subnets
resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.sentra.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index + 8)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = merge(local.common_tags, {
    Name = "sentra-${var.environment}-public-${var.availability_zones[count.index]}"
    Type = "public"
  })
}

# NAT Gateways
resource "aws_eip" "nat" {
  count  = length(var.availability_zones)
  domain = "vpc"
  tags   = merge(local.common_tags, { Name = "sentra-${var.environment}-nat-${count.index}" })
}

resource "aws_nat_gateway" "sentra" {
  count         = length(var.availability_zones)
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(local.common_tags, {
    Name = "sentra-${var.environment}-nat-${count.index}"
  })

  depends_on = [aws_internet_gateway.sentra]
}

# Route tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.sentra.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.sentra.id
  }

  tags = merge(local.common_tags, { Name = "sentra-${var.environment}-public-rt" })
}

resource "aws_route_table_association" "public" {
  count          = length(var.availability_zones)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  count  = length(var.availability_zones)
  vpc_id = aws_vpc.sentra.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.sentra[count.index].id
  }

  tags = merge(local.common_tags, {
    Name = "sentra-${var.environment}-private-rt-${count.index}"
  })
}

resource "aws_route_table_association" "private" {
  count          = length(var.availability_zones)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

# Default security group — deny all
resource "aws_default_security_group" "sentra" {
  vpc_id = aws_vpc.sentra.id

  tags = merge(local.common_tags, {
    Name = "sentra-${var.environment}-default-deny"
  })
}

# Security group: inter-service
resource "aws_security_group" "inter_service" {
  name        = "sentra-${var.environment}-inter-service"
  description = "Inter-service communication within the VPC"
  vpc_id      = aws_vpc.sentra.id

  ingress {
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "sentra-${var.environment}-inter-service"
  })
}

# Security group: database
resource "aws_security_group" "database" {
  name        = "sentra-${var.environment}-database"
  description = "Database access from VPC only"
  vpc_id      = aws_vpc.sentra.id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "sentra-${var.environment}-database"
  })
}

# Security group: cache
resource "aws_security_group" "cache" {
  name        = "sentra-${var.environment}-cache"
  description = "Cache access from VPC only"
  vpc_id      = aws_vpc.sentra.id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "sentra-${var.environment}-cache"
  })
}

# VPC Flow Logs
resource "aws_flow_log" "sentra" {
  vpc_id                   = aws_vpc.sentra.id
  traffic_type             = "ALL"
  log_destination_type     = "cloud-watch-logs"
  log_destination          = aws_cloudwatch_log_group.vpc_flow.arn
  iam_role_arn             = aws_iam_role.flow_logs.arn
  max_aggregation_interval = 60

  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "vpc_flow" {
  name              = "/aws/vpc/sentra-${var.environment}-flow"
  retention_in_days = var.environment == "production" ? 30 : 7
  tags              = local.common_tags
}

resource "aws_iam_role" "flow_logs" {
  name = "sentra-${var.environment}-flow-logs"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "vpc-flow-logs.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "flow_logs" {
  name = "sentra-${var.environment}-flow-logs-policy"
  role = aws_iam_role.flow_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
      ]
      Resource = "*"
    }]
  })
}
