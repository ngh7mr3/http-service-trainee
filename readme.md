## Task

Create an HTTP-service which can rate limit requests from one IPv4 subnet.
Service should provide any static content without limiting.

### Requirements

- Language - Python or Go
- RFC 6585 service answer
- IP should be extracted from X-Forwarded-For header
- Subnet - /24 (mask 255.255.255.0)
- Rate limit - 100 requests per minute
- Timeout after limiting - 2 minutes

### Bonus

- Test coverage
- Start up the service by 'docker-compose up'
- Include subnet size, rate limit and timeout at service start
- External(?) handler for manual reset any limits by subnet prefix
