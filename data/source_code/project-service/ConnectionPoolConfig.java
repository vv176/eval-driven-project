package com.clouddesk.project.config;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import javax.sql.DataSource;

@Slf4j
@Configuration
public class ConnectionPoolConfig {

    private static final int POOL_SIZE = 20;
    private static final long CONNECTION_TIMEOUT_MS = 30_000L;
    private static final long IDLE_TIMEOUT_MS = 600_000L;
    private static final long MAX_LIFETIME_MS = 1_800_000L;
    private static final long LEAK_DETECTION_THRESHOLD_MS = 60_000L;

    @Value("${spring.datasource.url}")
    private String jdbcUrl;

    @Value("${spring.datasource.username}")
    private String username;

    @Value("${spring.datasource.password}")
    private String password;

    @Value("${spring.datasource.driver-class-name:org.postgresql.Driver}")
    private String driverClassName;

    @Bean
    public DataSource dataSource() {
        log.info("Initializing HikariCP connection pool: poolSize={}, connectionTimeout={}ms",
                POOL_SIZE, CONNECTION_TIMEOUT_MS);

        final HikariConfig config = new HikariConfig();
        config.setJdbcUrl(jdbcUrl);
        config.setUsername(username);
        config.setPassword(password);
        config.setDriverClassName(driverClassName);

        config.setMaximumPoolSize(POOL_SIZE);
        config.setMinimumIdle(POOL_SIZE / 2);
        config.setConnectionTimeout(CONNECTION_TIMEOUT_MS);
        config.setIdleTimeout(IDLE_TIMEOUT_MS);
        config.setMaxLifetime(MAX_LIFETIME_MS);
        config.setLeakDetectionThreshold(LEAK_DETECTION_THRESHOLD_MS);

        config.setPoolName("clouddesk-project-pool");
        config.setAutoCommit(false);
        config.setConnectionTestQuery("SELECT 1");

        config.addDataSourceProperty("cachePrepStmts", "true");
        config.addDataSourceProperty("prepStmtCacheSize", "256");
        config.addDataSourceProperty("prepStmtCacheSqlLimit", "2048");
        config.addDataSourceProperty("useServerPrepStmts", "true");

        log.info("HikariCP pool configured: idleTimeout={}ms, maxLifetime={}ms, leakDetection={}ms",
                IDLE_TIMEOUT_MS, MAX_LIFETIME_MS, LEAK_DETECTION_THRESHOLD_MS);

        return new HikariDataSource(config);
    }
}
