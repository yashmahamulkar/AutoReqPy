import { Container } from "../shared/Container";
import { Title } from "../shared/Title";

const logos = ["python", "gemini", "github"];

export const Brands = () => {
  return (
    <section>
      <Container className="space-y-8">
        <div className="text-center max-w-3xl mx-auto">
          <Title>Integrated Service with</Title>
        </div>
        <div className="flex justify-center flex-wrap gap-8">
          {logos.map((logo, key) => (
            <div
              key={key}
              className="p-8 sm:p-10 rounded-xl bg-body border border-box-border group"
            >
              <img
                src={`/assets/logos/${logo}.png`}
                width="120"
                height="120"
                alt={logo}
                className="h-24 sm:h-28 w-auto ease-linear duration-300 grayscale group-hover:!grayscale-0 group-hover:scale-105"
              />
            </div>
          ))}
        </div>
      </Container>
    </section>
  );
};
