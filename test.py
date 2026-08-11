from openelectricity import OpenElectricityClient


# Initialize the client
client = OpenElectricityClient()

# Get energy data for the NEM
datatable = client.get_network_data('NEM', ['energy'], {
  interval: '1h',
  dateStart: '2024-01-01T00:00:00',
  dateEnd: '2024-01-02T00:00:00',
  primaryGrouping: 'network_region',
})