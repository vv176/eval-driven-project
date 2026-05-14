package com.clouddesk.gateway;

import javax.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

@Component
public class RequestRouter {

    private static final Logger log = LoggerFactory.getLogger(RequestRouter.class);

    private static final String HEADER_REGION = "X-CloudDesk-Region";
    private static final String HEADER_CUSTOMER_ID = "X-Customer-Id";
    private static final String HEADER_ACCOUNT_TIER = "X-Account-Tier";
    private static final String GDPR_COMPLIANCE_PREFIX = "/compliance/gdpr";

    private final GatewayConfig gatewayConfig;
    private final RateLimiter rateLimiter;
    private final RestTemplate restTemplate;

    public RequestRouter(final GatewayConfig gatewayConfig,
                         final RateLimiter rateLimiter,
                         final RestTemplate restTemplate) {
        this.gatewayConfig = gatewayConfig;
        this.rateLimiter = rateLimiter;
        this.restTemplate = restTemplate;
    }

    public ResponseEntity<String> routeRequest(final HttpServletRequest request) {
        final String customerId = request.getHeader(HEADER_CUSTOMER_ID);
        final String accountTier = request.getHeader(HEADER_ACCOUNT_TIER);
        final String path = request.getRequestURI();

        log.info("Routing request: path={}, customerId={}", path, customerId);

        if (!rateLimiter.isAllowed(customerId, accountTier)) {
            log.warn("Rate limit exceeded for customer={}, tier={}", customerId, accountTier);
            return ResponseEntity.status(429).body("{\"error\":\"Rate limit exceeded\"}");
        }

        final String region = getRegionFromRequest(request);
        final String targetUrl = resolveTargetService(path);

        if (targetUrl == null) {
            log.warn("No service mapping found for path={}", path);
            return ResponseEntity.status(404).body("{\"error\":\"Service not found\"}");
        }

        final String finalUrl = applyRegionRouting(targetUrl, path, region);
        log.info("Resolved target: url={}, region={}", finalUrl, region);

        final HttpHeaders headers = forwardHeaders(request);
        final HttpEntity<String> entity = new HttpEntity<>(headers);

        return restTemplate.exchange(
                finalUrl,
                HttpMethod.valueOf(request.getMethod()),
                entity,
                String.class
        );
    }

    public String getRegionFromRequest(final HttpServletRequest request) {
        final String regionHeader = request.getHeader(HEADER_REGION);
        if (regionHeader != null && !regionHeader.isBlank()) {
            return regionHeader.trim().toUpperCase();
        }
        return "US";
    }

    private String resolveTargetService(final String path) {
        if (path.startsWith("/api/v1/projects") || path.startsWith("/api/v1/workspaces")) {
            return gatewayConfig.getProjectServiceUrl();
        } else if (path.startsWith("/api/v1/tasks") || path.startsWith("/api/v1/sprints")) {
            return gatewayConfig.getTaskServiceUrl();
        } else if (path.startsWith("/api/v1/search")) {
            return gatewayConfig.getSearchServiceUrl();
        } else if (path.startsWith("/api/v1/auth")) {
            return gatewayConfig.getAuthServiceUrl();
        }
        return null;
    }

    private String applyRegionRouting(final String baseUrl, final String path, final String region) {
        if ("EU".equals(region) || "EU-WEST".equals(region) || "EU-CENTRAL".equals(region)) {
            log.info("Applying GDPR compliance routing for region={}", region);
            return baseUrl + GDPR_COMPLIANCE_PREFIX + path;
        }
        return baseUrl + path;
    }

    private HttpHeaders forwardHeaders(final HttpServletRequest request) {
        final HttpHeaders headers = new HttpHeaders();
        headers.set(HEADER_CUSTOMER_ID, request.getHeader(HEADER_CUSTOMER_ID));
        headers.set(HEADER_ACCOUNT_TIER, request.getHeader(HEADER_ACCOUNT_TIER));
        headers.set(HEADER_REGION, request.getHeader(HEADER_REGION));
        headers.set("Authorization", request.getHeader("Authorization"));
        headers.set("X-Request-Id", request.getHeader("X-Request-Id"));
        return headers;
    }
}
