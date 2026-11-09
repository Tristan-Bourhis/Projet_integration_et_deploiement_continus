variable "region" {
  description = "Région AWS de déploiement"
  type        = string
  default     = "eu-west-3"
}

variable "instance_type" {
  description = "VM hébergeant Docker, PostgreSQL et SeaweedFS"
  type        = string
  default     = "t3.small"
}

variable "ssh_public_key" {
  description = "Clé publique SSH ; ne jamais fournir la clé privée"
  type        = string
  validation {
    condition     = can(regex("^ssh-(ed25519|rsa) ", var.ssh_public_key))
    error_message = "Fournir une clé publique OpenSSH ed25519 ou RSA."
  }
}

variable "ssh_allowed_cidrs" {
  description = "CIDR IPv4 d'administration et du runner CD avec IP de sortie fixe"
  type        = list(string)
  validation {
    condition = length(var.ssh_allowed_cidrs) > 0 && alltrue([
      for cidr in var.ssh_allowed_cidrs :
      can(cidrnetmask(cidr)) && cidr != "0.0.0.0/0"
    ])
    error_message = "Fournir des CIDR IPv4 valides et restreints ; 0.0.0.0/0 est interdit."
  }
}
