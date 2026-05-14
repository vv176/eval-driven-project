package com.clouddesk.auth.service;

import com.clouddesk.auth.dto.TokenResponse;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.SignatureAlgorithm;
import io.jsonwebtoken.security.Keys;
import java.security.Key;
import java.util.Date;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class TokenService {

    private static final Logger log = LoggerFactory.getLogger(TokenService.class);

    private static final long ACCESS_TOKEN_EXPIRY_MS = 15 * 60 * 1000L;
    private static final long REFRESH_TOKEN_EXPIRY_MS = 7 * 24 * 60 * 60 * 1000L;

    private final Key signingKey;
    private final AuthenticationProvider authenticationProvider;

    public TokenService(@Value("${clouddesk.auth.jwt-secret}") final String jwtSecret,
                        final AuthenticationProvider authenticationProvider) {
        this.signingKey = Keys.hmacShaKeyFor(jwtSecret.getBytes());
        this.authenticationProvider = authenticationProvider;
    }

    public TokenResponse generateToken(final String email, final String password) {
        final String userId = authenticationProvider.authenticate(email, password);
        if (userId == null) {
            return null;
        }

        final String sessionId = UUID.randomUUID().toString();
        final String accessToken = buildToken(userId, sessionId, ACCESS_TOKEN_EXPIRY_MS);
        final String refreshToken = buildToken(userId, sessionId, REFRESH_TOKEN_EXPIRY_MS);

        log.info("Generated tokens for userId={}, sessionId={}", userId, sessionId);
        return new TokenResponse(userId, sessionId, accessToken, refreshToken);
    }

    public boolean validateToken(final String token) {
        try {
            final Claims claims = parseToken(token);
            final Date expiration = claims.getExpiration();
            return expiration.after(new Date());
        } catch (final ExpiredJwtException e) {
            log.warn("Token expired at={}", e.getClaims().getExpiration());
            return false;
        } catch (final Exception e) {
            log.error("Token validation failed: {}", e.getMessage());
            return false;
        }
    }

    public TokenResponse refreshToken(final String refreshToken) {
        final Claims claims = parseToken(refreshToken);
        final String userId = claims.getSubject();
        final String sessionId = claims.get("sessionId", String.class);

        final String newAccessToken = buildToken(userId, sessionId, ACCESS_TOKEN_EXPIRY_MS);
        final String newRefreshToken = buildToken(userId, sessionId, REFRESH_TOKEN_EXPIRY_MS);

        log.info("Refreshed tokens for userId={}, sessionId={}", userId, sessionId);
        return new TokenResponse(userId, sessionId, newAccessToken, newRefreshToken);
    }

    public String extractUserId(final String token) {
        try {
            return parseToken(token).getSubject();
        } catch (final Exception e) {
            log.error("Failed to extract userId from token: {}", e.getMessage());
            return null;
        }
    }

    public String extractSessionId(final String token) {
        try {
            return parseToken(token).get("sessionId", String.class);
        } catch (final Exception e) {
            log.error("Failed to extract sessionId from token: {}", e.getMessage());
            return null;
        }
    }

    private String buildToken(final String userId, final String sessionId, final long expiryMs) {
        final Date now = new Date();
        return Jwts.builder()
                .setSubject(userId)
                .claim("sessionId", sessionId)
                .setIssuedAt(now)
                .setExpiration(new Date(now.getTime() + expiryMs))
                .signWith(signingKey, SignatureAlgorithm.HS256)
                .compact();
    }

    private Claims parseToken(final String token) {
        return Jwts.parserBuilder()
                .setSigningKey(signingKey)
                .build()
                .parseClaimsJws(token)
                .getBody();
    }
}
