output "vnet_id" {
  description = "Virtual network id."
  value       = azurerm_virtual_network.this.id
}

output "subnet_ids" {
  description = "Subnet id per tier (public, app, data)."
  value       = { for tier, subnet in azurerm_subnet.this : tier => subnet.id }
}
