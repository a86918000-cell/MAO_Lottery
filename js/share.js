function drawShareImage(title, subtitle, rows) {
  const canvas = document.createElement("canvas");
  const width = 1080, padding = 64, rowHeight = 165;
  const height = Math.max(900, 300 + rows.length * rowHeight + 120);
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");

  ctx.fillStyle = "#f6f7f9";
  ctx.fillRect(0, 0, width, height);

  ctx.fillStyle = "#172033";
  ctx.font = "bold 62px sans-serif";
  ctx.fillText(title, padding, 110);

  ctx.fillStyle = "#687386";
  ctx.font = "bold 34px sans-serif";
  ctx.fillText(subtitle, padding, 170);

  let y = 245;
  rows.forEach(row => {
    ctx.fillStyle = "#ffffff";
    roundRect(ctx, padding, y - 52, width - padding * 2, 138, 24);

    ctx.fillStyle = "#172033";
    ctx.font = "bold 32px sans-serif";
    ctx.fillText(row.date || "", padding + 28, y - 5);

    const nums = (row.numbers || []).map(n => String(n).padStart(2, "0")).join("   ");
    ctx.fillStyle = "#155eef";
    ctx.font = "bold 42px sans-serif";
    ctx.fillText(nums, padding + 28, y + 48);

    if (row.specialNumber != null) {
      ctx.fillStyle = "#a66a00";
      ctx.font = "bold 28px sans-serif";
      ctx.fillText(`特別號  ${String(row.specialNumber).padStart(2, "0")}`, padding + 28, y + 88);
    }
    y += rowHeight;
  });

  ctx.fillStyle = "#687386";
  ctx.font = "28px sans-serif";
  ctx.fillText("開獎資訊僅供查詢，請以官方公告為準", padding, height - 55);

  return new Promise(resolve => canvas.toBlob(resolve, "image/png"));
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
  ctx.fill();
}

async function shareRows(title, subtitle, rows) {
  try {
    const blob = await drawShareImage(title, subtitle, rows);
    if (!blob) throw new Error("圖片產生失敗");

    const file = new File([blob], "開獎紀錄.png", { type: "image/png" });

    if (navigator.share && navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({ files: [file], title });
      return;
    }

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "開獎紀錄.png";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
    alert("此瀏覽器不支援直接分享圖片，已改為下載 PNG 圖片。");
  } catch (error) {
    if (error.name !== "AbortError") {
      console.error(error);
      alert(`圖片分享失敗：${error.message || error}`);
    }
  }
}
