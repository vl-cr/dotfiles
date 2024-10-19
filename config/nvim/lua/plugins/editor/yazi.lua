return {
    "mikavilpas/yazi.nvim",
    event = "VeryLazy",
    keys = {
        {
            "<leader>yy",
            ":Yazi cwd<CR>",
            desc = "CWD",
        },
        {
            "<leader>yf",
            ":Yazi<CR>",
            desc = "File",
        },
        {
            "<leader>ys",
            ":Yazi toggle<CR>",
            desc = "Resume last Yazi session",
        },
    },

    opts = {
        open_for_directories = false, -- Open yazi instead of netrw
        keymaps = {
            show_help = "<f1>",
        },
    },
}
