<template>
  <svg width="0" height="0" aria-hidden="true" style="display: none">
    <defs>
      <filter
        id="glitch-filter"
        x="-20%"
        y="-20%"
        width="140%"
        height="140%"
        filterUnits="objectBoundingBox"
        primitiveUnits="objectBoundingBox"
        color-interpolation-filters="sRGB"
      >
        <feImage
          id="glitch-canvas-map"
          x="0"
          y="0"
          width="1"
          height="1"
          preserveAspectRatio="none"
          result="canvas-map"
        />

        <feDisplacementMap
          id="glitch-displacement"
          in="SourceGraphic"
          in2="canvas-map"
          scale="0.045"
          xChannelSelector="R"
          yChannelSelector="G"
          result="displaced"
        />

        <feColorMatrix
          in="displaced"
          type="matrix"
          values="
            1 0 0 0 0
            0 0 0 0 0
            0 0 0 0 0
            0 0 0 1 0
          "
          result="red"
        />

        <feOffset in="red" dx="-0.001" dy="0" result="red-shifted" />

        <feColorMatrix
          in="displaced"
          type="matrix"
          values="
            0 0 0 0 0
            0 1 0 0 0
            0 0 0 0 0
            0 0 0 1 0
          "
          result="green"
        />

        <feOffset in="green" dx="0.001" dy="0" result="green-shifted" />

        <feColorMatrix
          in="displaced"
          type="matrix"
          values="
            0 0 0 0 0
            0 0 0 0 0
            0 0 1 0 0
            0 0 0 1 0
          "
          result="blue"
        />

        <feBlend in="red-shifted" in2="green-shifted" mode="screen" result="rg" />
        <feBlend in="rg" in2="blue" mode="screen" />
      </filter>
    </defs>
  </svg>
</template>
