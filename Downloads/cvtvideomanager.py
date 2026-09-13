import os
import io
import zipfile
import json
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox
import vlc
from moviepy import VideoFileClip

class CVTFormat:
    CHUNK_SIZE_LIMIT = 128 * 1024 * 1024 

    @staticmethod
    def convert_mp4_to_cvt(mp4_path, output_cvt_path):
        """
        Converts an MP4 file into a .cvt Compressed package by splitting 
        both video and audio streams into matching ~128MB segments.
        """
        if not mp4_path or not output_cvt_path:
            return False

        print(f"Initializing Video conversion for {mp4_path}...")
        
        main_clip = VideoFileClip(mp4_path)
        total_duration = main_clip.duration
        fps = main_clip.fps
        width, height = main_clip.size
        
        temp_dir = tempfile.gettempdir()
        chunk_index = 0
        temp_files = []
        
        file_size_bytes = os.path.getsize(mp4_path)
        bytes_per_second = file_size_bytes / total_duration
        seconds_per_chunk = (CVTFormat.CHUNK_SIZE_LIMIT * 0.9) / bytes_per_second 
        
        start_time = 0
        while start_time < total_duration:
            end_time = min(start_time + seconds_per_chunk, total_duration)
            current_temp_path = os.path.join(temp_dir, f"part_{chunk_index}.mp4")
            
            print(f"Slicing chunk {chunk_index} ({start_time:.1f}s to {end_time:.1f}s)...")
            sub_clip = main_clip.subclipped(start_time, end_time)
            
            sub_clip.write_videofile(
                current_temp_path, 
                codec="libx264", 
                audio_codec="aac",
                logger=None
            )
            
            temp_files.append(current_temp_path)
            start_time = end_time
            chunk_index += 1

        main_clip.close()

        metadata = {
            "total_chunks": len(temp_files),
            "original_fps": fps,
            "resolution": f"{width}x{height}",
            "format_version": "2.0_AudioEnabled"
        }

        print(f"Packing sub-segments and audio blocks into {output_cvt_path}...")
        with zipfile.ZipFile(output_cvt_path, 'w', zipfile.ZIP_STORED) as cvt_zip:
            cvt_zip.writestr("meta.json", json.dumps(metadata, indent=4))
            
            for index, file_path in enumerate(temp_files):
                cvt_zip.write(file_path, arcname=f"{index}.mp4")
                
        for file_path in temp_files:
            try: os.remove(file_path)
            except OSError: pass
            
        print("Conversion Successful!")
        return True

    @staticmethod
    def play_cvt(cvt_path):
        """
        Reads a .cvt file, extracts individual A/V fragments into RAM 
        and pipes them to a synchronized player layer with system controls.
        """
        if not cvt_path or not os.path.exists(cvt_path):
            return

        print(f"Reading target package metadata: {cvt_path}")
        
        with zipfile.ZipFile(cvt_path, 'r') as cvt_zip:
            meta_data = json.loads(cvt_zip.read("meta.json").decode('utf-8'))
            print(f"Metadata Found - Resolution: {meta_data['resolution']}, Segments: {meta_data['total_chunks']}")
            
            valid_files = [f for f in cvt_zip.namelist() if f.endswith('.mp4')]
            
            # FIX: Added [0] to the end of the split to extract just the number string before passing to int()
            chunk_names = sorted(valid_files, key=lambda x: int(os.path.basename(x).split('.')[0]))
            
            vlc_instance = vlc.Instance("--quiet", "--no-video-title-show")
            player = vlc_instance.media_player_new()
            
            print("\n=== SYSTEM CONTROLS ===")
            print("Use the native VLC playback window wrapper.")
            print("Press Close (X) or stop via IDE terminal to exit.")
            print("=======================\n")

            for chunk_name in chunk_names:
                print(f"Streaming package block {chunk_name} into system memory layer...")
                
                chunk_data = cvt_zip.read(chunk_name)
                ram_buffer = io.BytesIO(chunk_data)
                
                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as ram_file:
                    ram_file.write(ram_buffer.read())
                    ram_file_path = ram_file.name

                media = vlc_instance.media_new(ram_file_path)
                player.set_media(media)
                player.play()
                
                import time
                time.sleep(0.5) 
                
                while player.get_state() in [vlc.State.Playing, vlc.State.Paused, vlc.State.Opening]:
                    time.sleep(0.1)
                            
                try: os.remove(ram_file_path)
                except OSError: pass

        print("Finished playback")


# --- GUI Framework Wrap Engine ---
class CVTGuiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CVT Media")
        self.root.geometry("450x300")
        self.root.configure(bg="#212121")
        self.root.resizable(False, False)

        self.label = tk.Label(root, text="Compressed Video Type ", font=("Helvetica", 16, "bold"), fg="#E0E0E0", bg="#212121")
        self.label.pack(pady=20)
        
        self.sub_label = tk.Label(root, text="Complete Audio & Memory Streaming(RAM)", font=("Helvetica", 9), fg="#B0B0B0", bg="#212121")
        self.sub_label.pack(pady=5)

        self.btn_convert = tk.Button(root, text="Convert MP4 (Include Sound)", command=self.handle_conversion, width=28, height=2, bg="#2E7D32", fg="white", font=("Helvetica", 10, "bold"), relief="flat")
        self.btn_convert.pack(pady=10)

        self.btn_play = tk.Button(root, text="Stream .cvt Player", command=self.handle_playback, width=28, height=2, bg="#1565C0", fg="white", font=("Helvetica", 10, "bold"), relief="flat")
        self.btn_play.pack(pady=10)

    def handle_conversion(self):
        input_mp4 = filedialog.askopenfilename(title="Select Input Video", filetypes=[("MP4 Video Files", "*.mp4")])
        if not input_mp4: return

        output_cvt = filedialog.asksaveasfilename(
            title="Save CVT File As", 
            defaultextension=".cvt", 
            filetypes=[("Compressed Video Type", "*.cvt")]
        )
        if not output_cvt: return

        self.btn_convert.config(text="Processing Audio Channel...", state="disabled", bg="#555555")
        self.root.update()
        
        success = CVTFormat.convert_mp4_to_cvt(input_mp4, output_cvt)
        
        self.btn_convert.config(text="Convert MP4 to CVT", state="normal", bg="#2E7D32")
        if success:
            messagebox.showinfo("Success", "Compiled mp4 into cvt")

    def handle_playback(self):
        target_cvt = filedialog.askopenfilename(title="Select CVT File to Play", filetypes=[("Compressed Video Type", "*.cvt")])
        if not target_cvt: return
        CVTFormat.play_cvt(target_cvt)

if __name__ == "__main__":
    window = tk.Tk()
    app = CVTGuiApp(window)
    window.mainloop()
