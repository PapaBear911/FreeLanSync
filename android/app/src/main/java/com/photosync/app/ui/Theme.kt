package com.photosync.app.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// FreeLanSync Cyber Dark Palette
private val FreeLanSyncDarkColorScheme = darkColorScheme(
    primary = Color(0xFF6366F1), // Indigo 500
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFF1E1B4B), // Deep Indigo
    onPrimaryContainer = Color(0xFFC7D2FE),
    secondary = Color(0xFF38BDF8), // Sky / Cyan 400
    onSecondary = Color(0xFF031525),
    secondaryContainer = Color(0xFF0C4A6E),
    onSecondaryContainer = Color(0xFFBAE6FD),
    tertiary = Color(0xFF30D158), // Apple Emerald
    onTertiary = Color(0xFF00210A),
    background = Color(0xFF070A11), // Obsidian Black
    onBackground = Color(0xFFF8FAFC),
    surface = Color(0xFF0F172A), // Slate 900 Glass
    onSurface = Color(0xFFF8FAFC),
    surfaceVariant = Color(0xFF1E293B), // Slate 800
    onSurfaceVariant = Color(0xFF94A3B8), // Slate 400
    outline = Color(0xFF334155),
    outlineVariant = Color(0xFF1E293B),
    error = Color(0xFFFF453A),
    onError = Color(0xFFFFFFFF)
)

private val FreeLanSyncLightColorScheme = lightColorScheme(
    primary = Color(0xFF4F46E5),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFEEF2FF),
    onPrimaryContainer = Color(0xFF312E81),
    secondary = Color(0xFF0284C7),
    onSecondary = Color(0xFFFFFFFF),
    secondaryContainer = Color(0xFFE0F2FE),
    onSecondaryContainer = Color(0xFF0369A1),
    tertiary = Color(0xFF16A34A),
    background = Color(0xFFF8FAFC),
    onBackground = Color(0xFF0F172A),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF0F172A),
    surfaceVariant = Color(0xFFF1F5F9),
    onSurfaceVariant = Color(0xFF64748B),
    outline = Color(0xFFCBD5E1),
    error = Color(0xFFDC2626)
)

@Composable
fun FreeLanSyncTheme(
    darkTheme: Boolean = true, // Default to sleek dark glass aesthetic
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) FreeLanSyncDarkColorScheme else FreeLanSyncLightColorScheme
    MaterialTheme(
        colorScheme = colorScheme,
        content = content
    )
}
