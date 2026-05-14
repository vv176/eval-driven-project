package com.clouddesk.auth.controller;

import com.clouddesk.auth.dto.LoginRequest;
import com.clouddesk.auth.dto.RefreshRequest;
import com.clouddesk.auth.dto.TokenResponse;
import com.clouddesk.auth.service.TokenService;
import com.clouddesk.auth.service.SessionStore;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {

    private static final Logger log = LoggerFactory.getLogger(AuthController.class);

    private final TokenService tokenService;
    private final SessionStore sessionStore;

    public AuthController(final TokenService tokenService, final SessionStore sessionStore) {
        this.tokenService = tokenService;
        this.sessionStore = sessionStore;
    }

    @PostMapping("/login")
    public ResponseEntity<TokenResponse> login(@RequestBody final LoginRequest request) {
        log.info("Login attempt for user={}", request.getEmail());

        final TokenResponse tokenResponse = tokenService.generateToken(
                request.getEmail(), request.getPassword()
        );

        if (tokenResponse == null) {
            log.warn("Failed login attempt for user={}", request.getEmail());
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }

        sessionStore.createSession(tokenResponse.getUserId(), tokenResponse.getSessionId());
        log.info("Login successful for user={}, sessionId={}", request.getEmail(), tokenResponse.getSessionId());

        return ResponseEntity.ok(tokenResponse);
    }

    @PostMapping("/refresh")
    public ResponseEntity<TokenResponse> refresh(@RequestBody final RefreshRequest request) {
        final String refreshToken = request.getRefreshToken();
        log.info("Token refresh requested");

        if (!tokenService.validateToken(refreshToken)) {
            log.warn("Invalid refresh token presented");
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        }

        final TokenResponse tokenResponse = tokenService.refreshToken(refreshToken);
        return ResponseEntity.ok(tokenResponse);
    }

    @PostMapping("/logout")
    public ResponseEntity<Void> logout(@RequestHeader("Authorization") final String authHeader) {
        final String token = authHeader.replace("Bearer ", "");
        log.info("Logout requested");

        final String userId = tokenService.extractUserId(token);
        final String sessionId = tokenService.extractSessionId(token);

        if (userId != null && sessionId != null) {
            sessionStore.invalidateSession(userId, sessionId);
            log.info("Session invalidated for user={}, sessionId={}", userId, sessionId);
        }

        return ResponseEntity.noContent().build();
    }
}
