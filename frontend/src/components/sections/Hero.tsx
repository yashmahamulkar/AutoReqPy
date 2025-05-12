import { useState } from "react";
import { Button } from "../shared/Button";
import { Container } from "../shared/Container";
import { Paragraph } from "../shared/Paragraph";


export const Hero = () => {
  const [githubUrl, setGithubUrl] = useState("");
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(false);


  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    setResult("");

    try {
      const response = await fetch("http://127.0.0.1:5000/clone-repo/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ github_url: githubUrl }),
      });

      if (!response.ok) throw new Error("API request failed");

      const json = await response.json();
      setResult(json["requirements.txt"]);
    } catch (err) {

    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="relative pt-32 lg:pt-36">
      <Container className="flex flex-col items-center text-center gap-10">
        <div className="absolute w-full inset-y-0">
          {/* Decorative spans here */}
        </div>

        <div className="relative flex flex-col items-center text-center max-w-3xl mx-auto">
<h1 className="text-heading-1 text-2xl sm:text-3xl md:text-4xl xl:text-5xl font-bold leading-tight">
  Instantly Generate 
  <br />
  <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-violet-600 ml-2">
    Dependency List<br />
  </span>
  from GitHub Repos 
</h1>

<Paragraph className="mt-4 text-sm sm:text-base leading-relaxed">
  Simplify Python dependency management with AutoReqPy. Just provide a repo link, and we’ll handle the rest.
</Paragraph>




          <div className="mt-10 w-full flex max-w-xl mx-auto">
            <form
              onSubmit={handleSubmit}
              className="py-1 pl-6 w-full pr-1 flex gap-3 items-center text-heading-3
                         shadow-lg shadow-box-shadow border border-box-border
                         bg-box-bg rounded-full ease-linear focus-within:bg-body
                         focus-within:border-primary"
            >
              <span className="min-w-max pr-2 border-r border-box-border">
                {/* Optional: GitHub icon */}
              </span>
              <input
                type="url"
                placeholder="https://github.com/username/repo.git"
                value={githubUrl}
                onChange={(e) => setGithubUrl(e.target.value)}
                required
                className="w-full py-3 outline-none bg-transparent"
              />
              <Button type="submit" className="min-w-max text-white">
                <span className="relative z-[5]">
                  {loading ? "Generating." : "Generate"}
                </span>
              </Button>
            </form>
          </div>

          {/* Output Section */}
{result && (
  <Container className="mt-10 flex justify-center">
    <div
      className="relative p-5 sm:p-6 max-w-5xl w-full rounded-3xl bg-box-bg
                 border border-box-border shadow-lg shadow-box-shadow text-left"
    >
      <button
        onClick={() => navigator.clipboard.writeText(result)}
        className="absolute top-4 right-4 text-xs bg-blue-600 text-white px-2 py-1 rounded hover:bg-blue-700"
      >
        Copy
      </button>
      <strong className="block mb-4 text-heading-3">requirements.txt</strong>
      <pre className="whitespace-pre-wrap text-sm text-heading-3">{result}</pre>
    </div>
  </Container>
)}


        </div>
      </Container>

    </section>
  );
};
