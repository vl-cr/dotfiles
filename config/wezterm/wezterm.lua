local wezterm = require("wezterm")

return {
    -- Visuals
    color_scheme = "Catppuccin Mocha",
    window_decorations = "RESIZE",
    initial_rows = 35,
    initial_cols = 120,
    window_background_opacity = 0.99,
    macos_window_background_blur = 40,

    -- Font
    font = wezterm.font { family = "FiraCode Nerd Font" },
    font_size = 12.5,

    -- Misc
    hide_tab_bar_if_only_one_tab = true,
    window_close_confirmation = "NeverPrompt",
    alternate_buffer_wheel_scroll_speed = 1,

    -- Keys
    keys = {
        {
            key = "F10",
            action = wezterm.action.ToggleFullScreen,
        },
        {
            key="LeftArrow", 
            mods="SHIFT",
            action=wezterm.action{SendString="\x1bb"}
        },
        {
            key="RightArrow", 
            mods="SHIFT",
            action=wezterm.action{SendString="\x1bf"}
        },
    },
}
