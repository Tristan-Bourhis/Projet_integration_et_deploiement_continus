output "public_ip" {
  description = "Adresse à configurer dans DEPLOY_HOST"
  value       = aws_eip.pipeline.public_ip
}

output "ssh_command" {
  value = "ssh ubuntu@${aws_eip.pipeline.public_ip}"
}
