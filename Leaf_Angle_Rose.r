---
title: "Leaf Angle Rose"
author: "Richard Slevin"
date: "2025-12-18"
output: html_document
---

```{r setup, include=FALSE}

library(readr)

leaf_angle <- read_csv("WitnessTree_LeafAngle_2025.csv")

head(leaf_angle)
str(leaf_angle)
colnames(leaf_angle)

#View(leaf_angle)

```



```{r}

library(dplyr)
library(tibble)
library(plotly)
library(base64enc)
library(png)


bins <- 18
binwidth <- 180 / bins

# ----------------------------
# Leaf PNGs (current directory)
# ----------------------------
leaf_up_file         <- "Leaf_Up.png"
leaf_horizontal_file <- "Leaf_Horizontal.png"
leaf_down_file       <- "Leaf_Down.png"

for (f in c(leaf_up_file, leaf_horizontal_file, leaf_down_file)) {
  if (!file.exists(f)) stop("File not found: ", f)
}

leaf_up_uri         <- paste0("data:image/png;base64,", base64enc::base64encode(leaf_up_file))
leaf_horizontal_uri <- paste0("data:image/png;base64,", base64enc::base64encode(leaf_horizontal_file))
leaf_down_uri       <- paste0("data:image/png;base64,", base64enc::base64encode(leaf_down_file))

# ----------------------------
# Loop all species
# ----------------------------
plot_list <- vector("list", length(leaf_angle))
names(plot_list) <- names(leaf_angle)

for (sp in names(leaf_angle)) {

  x_deg <- as.numeric(leaf_angle[[sp]])
  x_deg <- x_deg[is.finite(x_deg)]
  x_deg <- pmin(pmax(x_deg, -90), 90)

  if (length(x_deg) == 0) {
    plot_list[[sp]] <- NULL
    next
  }

  df_bin <- tibble(angle = x_deg) %>%
    mutate(
      angle_shift = pmin(pmax(angle + 90, 0), 180 - 1e-9),
      bin_left    = floor(angle_shift / binwidth) * binwidth,
      theta       = (bin_left + binwidth / 2) - 90
    ) %>%
    count(theta, name = "count")

  rmax <- max(df_bin$count)

  p <- plot_ly() %>%
    add_trace(
      data  = df_bin,
      type  = "barpolar",
      r     = ~count,
      theta = ~theta,
      width = binwidth,
      marker = list(
        color = "#2E7D32",
        line  = list(color = "black", width = 1)
      )
    ) %>%
    layout(
      title = list(
        text = paste0(sp, " (Laminar Tilt Angle)"),
        x = 0.5,
        y = 0.98
      ),
      showlegend = FALSE,

      images = list(
        list(
          source  = leaf_up_uri,
          xref    = "paper", yref = "paper",
          x       = 0.38, y = 0.96,
          sizex   = 0.06, sizey = 0.06,
          xanchor = "left", yanchor = "top",
          layer   = "above"
        ),
        list(
          source  = leaf_horizontal_uri,
          xref    = "paper", yref = "paper",
          x       = 0.66, y = 0.50,
          sizex   = 0.06, sizey = 0.06,
          xanchor = "left", yanchor = "top",
          layer   = "above"
        ),
        list(
          source  = leaf_down_uri,
          xref    = "paper", yref = "paper",
          x       = 0.38, y = 0.05,
          sizex   = 0.06, sizey = 0.06,
          xanchor = "left", yanchor = "top",
          layer   = "above"
        )
      ),

      polar = list(
        domain = list(
          x = c(0.05, 0.98),
          y = c(0.10, 0.85)
        ),
        sector = c(-90, 90),
        angularaxis = list(
          rotation  = 0,
          direction = "counterclockwise",
          thetaunit = "degrees"
        ),
        radialaxis = list(
          range = c(0, rmax),
          autorange = FALSE
        )
      ),

      annotations = list(
        list(
          text = "Count",
          xref = "paper",
          yref = "paper",
          x = 0.36,
          y = 0.24,
          showarrow = FALSE,
          textangle = 270,
          font = list(size = 12, color = "black")
        )
      )
    )

  plot_list[[sp]] <- p
}

# Print all plots
for (sp in names(plot_list)) {
  if (!is.null(plot_list[[sp]])) print(plot_list[[sp]])
}


```




```{r}
library(dplyr)
library(tibble)
library(plotly)
library(base64enc)
library(htmlwidgets)


bins <- 18
binwidth <- 180 / bins

# ----------------------------
# Leaf PNGs 
# ----------------------------
leaf_up_file         <- "Leaf_Up.png"
leaf_horizontal_file <- "Leaf_Horizontal.png"
leaf_down_file       <- "Leaf_Down.png"

for (f in c(leaf_up_file, leaf_horizontal_file, leaf_down_file)) {
  if (!file.exists(f)) stop("File not found: ", f)
}

leaf_up_uri         <- paste0("data:image/png;base64,", base64enc::base64encode(leaf_up_file))
leaf_horizontal_uri <- paste0("data:image/png;base64,", base64enc::base64encode(leaf_horizontal_file))
leaf_down_uri       <- paste0("data:image/png;base64,", base64enc::base64encode(leaf_down_file))

# ----------------------------
# Output folder
# ----------------------------
out_dir <- "leaf laminar angle tilt diagrams"
if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)

# helper: safe filenames
safe_name <- function(x) {
  x <- gsub("[/\\\\:*?\"<>|]", "_", x)  # Windows-illegal chars
  x <- gsub("\\s+", "_", x)            # spaces -> _
  x
}

# ----------------------------
# Loop all species
# ----------------------------
plot_list <- vector("list", length(leaf_angle))
names(plot_list) <- names(leaf_angle)

for (sp in names(leaf_angle)) {

  x_deg <- as.numeric(leaf_angle[[sp]])
  x_deg <- x_deg[is.finite(x_deg)]
  x_deg <- pmin(pmax(x_deg, -90), 90)

  if (length(x_deg) == 0) {
    plot_list[[sp]] <- NULL
    next
  }

  df_bin <- tibble(angle = x_deg) %>%
    mutate(
      angle_shift = pmin(pmax(angle + 90, 0), 180 - 1e-9),
      bin_left    = floor(angle_shift / binwidth) * binwidth,
      theta       = (bin_left + binwidth / 2) - 90
    ) %>%
    count(theta, name = "count")

  rmax <- max(df_bin$count)

  p <- plot_ly() %>%
    add_trace(
      data  = df_bin,
      type  = "barpolar",
      r     = ~count,
      theta = ~theta,
      width = binwidth,
      marker = list(
        color = "#2E7D32",
        line  = list(color = "black", width = 1)
      )
    ) %>%
    layout(
      title = list(
        text = paste0(sp),
        x = 0.5,
        y = 0.98
      ),
      showlegend = FALSE,

      images = list(
        list(
          source  = leaf_up_uri,
          xref    = "paper", yref = "paper",
          x       = 0.38, y = 0.96,
          sizex   = 0.06, sizey = 0.06,
          xanchor = "left", yanchor = "top",
          layer   = "above"
        ),
        list(
          source  = leaf_horizontal_uri,
          xref    = "paper", yref = "paper",
          x       = 0.66, y = 0.50,
          sizex   = 0.06, sizey = 0.06,
          xanchor = "left", yanchor = "top",
          layer   = "above"
        ),
        list(
          source  = leaf_down_uri,
          xref    = "paper", yref = "paper",
          x       = 0.38, y = 0.05,
          sizex   = 0.06, sizey = 0.06,
          xanchor = "left", yanchor = "top",
          layer   = "above"
        )
      ),

      polar = list(
        domain = list(
          x = c(0.05, 0.98),
          y = c(0.10, 0.85)
        ),
        sector = c(-90, 90),
        angularaxis = list(
          rotation  = 0,
          direction = "counterclockwise",
          thetaunit = "degrees"
        ),
        radialaxis = list(
          range = c(0, rmax),
          autorange = FALSE
        )
      ),

      annotations = list(
        list(
          text = "Count",
          xref = "paper",
          yref = "paper",
          x = 0.36,
          y = 0.24,
          showarrow = FALSE,
          textangle = 270,
          font = list(size = 12, color = "black")
        )
      )
    )

  plot_list[[sp]] <- p

  # ----------------------------
  # Save image 
  # ----------------------------

  file_html <- file.path(out_dir, paste0(safe_name(sp), "_laminar_tilt.html"))
  htmlwidgets::saveWidget(p, file_html, selfcontained = TRUE)

}

# Print all plots (optional)
for (sp in names(plot_list)) {
  if (!is.null(plot_list[[sp]])) print(plot_list[[sp]])
}


```

```{r}
library(webshot2)

file_html <- file.path(out_dir, paste0(safe_name(sp), "_laminar_tilt.html"))
file_pdf  <- file.path(out_dir, paste0(safe_name(sp), "_laminar_tilt.pdf"))

# Save widget
htmlwidgets::saveWidget(
  p,
  file_html,
  selfcontained = TRUE
)

# ---- wrapper HTML to enforce landscape + centering ----
wrapper_html <- file.path(out_dir, paste0(safe_name(sp), "_wrapper.html"))

wrapper <- sprintf(
'<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {
  size: A4 landscape;
  margin: 20mm;
}
html, body {
  width: 100%%;
  height: 100%%;
  margin: 0;
  padding: 0;
  overflow: hidden;
}
body {
  display: flex;
  justify-content: center;
  align-items: center;
}

/* Centered figure box – SMALLER */
.figure {
  width: 65%%;
  height: 65%%;
  display: flex;
  justify-content: center;
  align-items: center;
}

/* Fill the figure box, not the page */
iframe {
  border: none;
  width: 100%%;
  height: 100%%;
}
</style>
</head>
<body>
  <div class="figure">
    <iframe src="%s"></iframe>
  </div>
</body>
</html>',
basename(file_html)
)

writeLines(wrapper, wrapper_html)

# ---- render PDF ----
webshot2::webshot(
  url     = wrapper_html,
  file    = file_pdf,
  vwidth  = 1750,
  vheight = 1240,
  delay   = 1
)

# Open output folder
browseURL(normalizePath(out_dir))

```


```{r}
# -----------------------------
# One-page PNG contact sheet (base R + png)
# -----------------------------

# 1) Directory containing the PNG files
img_dir <- "Leaf Angle WTP"   # use full path if not in working directory

# 2) Output file (single-page PDF)
out_pdf <- file.path(img_dir, "Leaf_Angle_WTP_contact_sheet.pdf")

# 3) List PNGs (case-insensitive), sorted
png_files <- list.files(
  path = img_dir,
  pattern = "\\.png$",
  ignore.case = TRUE,
  full.names = TRUE
)
png_files <- sort(png_files)

if (length(png_files) == 0) {
  stop("No PNG files found in: ", normalizePath(img_dir, winslash = "/"))
}

# 4) Grid layout
n <- length(png_files)
ncol <- ceiling(sqrt(n))
nrow <- ceiling(n / ncol)

# Force 4 x 5 if exactly 20 images
if (n == 20) {
  nrow <- 5
  ncol <- 4
}

# 5) Create single-page PDF (A4 landscape)
pdf(out_pdf, width = 11.69, height = 8.27, onefile = TRUE)

op <- par(no.readonly = TRUE)
on.exit({
  par(op)
  dev.off()
}, add = TRUE)

par(
  mfrow = c(nrow, ncol),
  mar   = c(0.15, 0.15, 0.15, 0.15),
  oma   = c(0.6, 0.6, 0.6, 0.6),
  xaxs  = "i",
  yaxs  = "i"
)

# 6) Draw images (preserve aspect ratio + extra padding)
pad_scale <- 0.82   # smaller = more padding 

for (f in png_files) {
  img <- readPNG(f)

  h <- dim(img)[1]
  w <- dim(img)[2]
  img_asp <- h / w

  plot.new()

  if (img_asp >= 1) {
    # tall image
    width_norm <- (1 / img_asp) * pad_scale
    xpad <- (1 - width_norm) / 2
    ypad <- (1 - pad_scale) / 2
    rasterImage(img, xpad, ypad, 1 - xpad, 1 - ypad)
  } else {
    # wide image
    height_norm <- img_asp * pad_scale
    xpad <- (1 - pad_scale) / 2
    ypad <- (1 - height_norm) / 2
    rasterImage(img, xpad, ypad, 1 - xpad, 1 - ypad)
  }
}



# 7) Optional title
mtext("Leaf Angle WTP", outer = TRUE, line = -0.4, cex = 1)

message("Wrote: ", normalizePath(out_pdf, winslash = "/"))


```
