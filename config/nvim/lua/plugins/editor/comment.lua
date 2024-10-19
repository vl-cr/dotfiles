return {
    {
        "numToStr/Comment.nvim",
        event = { "BufReadPre", "BufNewFile" },
        opts = {
            padding = true, -- Add a space between comment and the line
            sticky = true, -- Keep cursor position when commenting
            ignore = nil, -- Lines to be ignored while commenting (can be a regex pattern)

            -- Normal mode mapping keys
            toggler = {
                line = "gcc", -- 'gcc' to comment/uncomment current line
                block = "gbc", -- 'gbc' to comment/uncomment current line using block comment
            },

            -- Operator-pending mappings for visual mode and motions
            opleader = {
                line = "gc", -- 'gc' as prefix for line commenting in visual mode or with motions (gc3j)
                block = "gb", -- 'gb' as prefix for block commenting in visual mode or with motions (gb3j)
            },
        },
    },
}
